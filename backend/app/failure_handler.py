from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional, Set

logger = logging.getLogger("backend.app.failure_handler")


# --- Domain Resilience Exceptions ---

class ResilienceError(Exception):
    """Base exception for platform resilience and failure handling."""
    status_code: int = 500
    error_code: str = "RESILIENCE_ERROR"

    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


class DatabaseUnavailableError(ResilienceError):
    """Raised when the database connection fails, is disconnected, or pool is exhausted."""
    status_code: int = 503
    error_code: str = "DATABASE_UNAVAILABLE"


class SimulatorExecutionError(ResilienceError):
    """Raised when the simulated payment gateway or adapter encounters an unexpected failure."""
    status_code: int = 502
    error_code: str = "SIMULATOR_FAILURE"


class MalformedEventError(ResilienceError):
    """Raised when an incoming event is missing required attributes or contains invalid data."""
    status_code: int = 400
    error_code: str = "MALFORMED_EVENT"


class CustomerNotFoundError(ResilienceError):
    """Raised when a customer cannot be identified and conservative fallback is triggered."""
    status_code: int = 404
    error_code: str = "CUSTOMER_NOT_FOUND"


class TransactionNotFoundError(ResilienceError):
    """Raised when a requested transaction is not found in database or simulator."""
    status_code: int = 404
    error_code: str = "TRANSACTION_NOT_FOUND"


class AlreadySuccessfulPaymentError(ResilienceError):
    """Raised when recovery is attempted on an already settled or successful transaction."""
    status_code: int = 400
    error_code: str = "PAYMENT_ALREADY_SUCCESSFUL"


class PendingPaymentUncertainStateError(ResilienceError):
    """Raised when payment is in an uncertain pending state; automated retry is prohibited."""
    status_code: int = 409
    error_code: str = "PAYMENT_PENDING_WAIT"


class AgentTimeoutError(ResilienceError):
    """Raised when an autonomous agent execution exceeds maximum allowable run duration."""
    status_code: int = 504
    error_code: str = "AGENT_TIMEOUT"


class ConcurrentRecoveryError(ResilienceError):
    """Raised when concurrent recovery requests are executed on the same transaction."""
    status_code: int = 409
    error_code: str = "CONCURRENT_RECOVERY_IN_PROGRESS"


class InvalidPaymentMethodError(ResilienceError):
    """Raised when an invalid or unauthorized payment instrument is specified."""
    status_code: int = 400
    error_code: str = "INVALID_PAYMENT_METHOD"


class UncertainPaymentStateError(ResilienceError):
    """Raised when payment state is indeterminate; further retries are prohibited by safety policy."""
    status_code: int = 409
    error_code: str = "UNCERTAIN_PAYMENT_STATE"


# --- Concurrent Recovery Lock Manager ---

class ConcurrentRecoveryManager:
    """Thread-safe manager tracking in-flight recovery executions per transaction_id.
    
    Prevents race conditions, double charging, and redundant agent executions.
    """

    def __init__(self):
        self._active_recoveries: Set[str] = set()
        self._lock = threading.Lock()

    def is_active(self, transaction_id: str) -> bool:
        with self._lock:
            return transaction_id in self._active_recoveries

    def acquire(self, transaction_id: str) -> None:
        with self._lock:
            if transaction_id in self._active_recoveries:
                logger.warning(
                    f"[CONCURRENCY ALERT] Concurrent recovery rejected for transaction: '{transaction_id}'"
                )
                raise ConcurrentRecoveryError(
                    f"Recovery operation is already in progress for transaction '{transaction_id}'. "
                    "Concurrent recovery requests are blocked to prevent duplicate transactions."
                )
            self._active_recoveries.add(transaction_id)
            logger.debug(f"Acquired recovery lock for transaction '{transaction_id}'")

    def release(self, transaction_id: str) -> None:
        with self._lock:
            self._active_recoveries.discard(transaction_id)
            logger.debug(f"Released recovery lock for transaction '{transaction_id}'")

    @contextmanager
    def guard(self, transaction_id: str) -> Generator[None, None, None]:
        self.acquire(transaction_id)
        try:
            yield
        finally:
            self.release(transaction_id)

    def clear(self) -> None:
        with self._lock:
            self._active_recoveries.clear()


_concurrency_mgr_instance: Optional[ConcurrentRecoveryManager] = None


def get_concurrent_recovery_manager() -> ConcurrentRecoveryManager:
    global _concurrency_mgr_instance
    if _concurrency_mgr_instance is None:
        _concurrency_mgr_instance = ConcurrentRecoveryManager()
    return _concurrency_mgr_instance


# --- Safe Recovery Guard ---

ALLOWED_PAYMENT_METHODS: Set[str] = {"UPI", "CARD", "NETBANKING", "WALLET"}
UNCERTAIN_PAYMENT_STATES: Set[str] = {"PENDING", "PROCESSING", "SUBMITTED", "IN_FLIGHT", "UNKNOWN"}


class SafeRecoveryGuard:
    """Guarantees safe state handling and enforces deterministic non-retry policies."""

    @staticmethod
    def validate_event_payload(event: Dict[str, Any]) -> None:
        """Enforces structural and numerical integrity on incoming payment events."""
        if not isinstance(event, dict):
            raise MalformedEventError("Event payload must be a valid dictionary/JSON object.")

        txn_id = event.get("transaction_id") or event.get("id")
        if not txn_id or not str(txn_id).strip():
            raise MalformedEventError("Field 'transaction_id' is mandatory and cannot be empty.")

        # Numerical bounds check
        if "amount" in event:
            try:
                amt = float(event["amount"])
                if amt <= 0:
                    raise MalformedEventError(f"Transaction amount must be strictly positive (got: {amt}).")
                if amt > 10_000_000.0:
                    raise MalformedEventError(f"Transaction amount exceeds maximum platform limit of ₹10,000,000 (got: {amt}).")
            except (ValueError, TypeError):
                raise MalformedEventError(f"Transaction amount must be a valid numeric float (got: {event.get('amount')}).")

        # Failure code sanitization
        fcode = event.get("failure_code")
        if fcode and not isinstance(fcode, str):
            raise MalformedEventError(f"failure_code must be a string value (got: {type(fcode).__name__}).")

    @staticmethod
    def assert_recoverable_status(transaction: Dict[str, Any]) -> None:
        """Validates that a transaction is in an actionable state.
        
        CRITICAL SAFETY CONSTRAINTS:
        1. If status is SUCCESS -> Reject recovery with AlreadySuccessfulPaymentError.
        2. If status is PENDING / PROCESSING -> Reject automated retry with PendingPaymentUncertainStateError.
        """
        status = str(transaction.get("status", "")).upper().strip()
        txn_id = transaction.get("transaction_id", "unknown")

        if status == "SUCCESS":
            logger.warning(f"[SAFETY VIOLATION PREVENTED] Attempted recovery on settled transaction '{txn_id}'")
            raise AlreadySuccessfulPaymentError(
                f"Transaction '{txn_id}' is already successfully settled. "
                "Further recovery attempts are strictly prohibited by safety policy (Rule POL-001)."
            )

        if status in UNCERTAIN_PAYMENT_STATES or transaction.get("failure_code") == "PAYMENT_PENDING":
            logger.info(f"[UNCERTAIN STATE DETECTED] Payment '{txn_id}' is pending settlement. Halting retries.")
            raise PendingPaymentUncertainStateError(
                f"Transaction '{txn_id}' is in pending settlement status ('{status}'). "
                "Automated payment retry is prohibited under uncertain payment states to prevent double-charging. "
                "Wait and poll gateway status instead (Rule POL-007)."
            )

    @staticmethod
    def is_uncertain_state(status: str, failure_code: Optional[str] = None) -> bool:
        """Evaluates whether the payment state is indeterminate."""
        stat_upper = str(status or "").upper().strip()
        fcode_upper = str(failure_code or "").upper().strip()
        return (stat_upper in UNCERTAIN_PAYMENT_STATES) or (fcode_upper in {"PAYMENT_PENDING", "GATEWAY_TIMEOUT_AMBIGUOUS"})

    @staticmethod
    def validate_payment_method(method: str) -> None:
        """Validates that the payment instrument belongs to the approved platform methods."""
        m_upper = str(method or "").upper().strip()
        if not m_upper or m_upper not in ALLOWED_PAYMENT_METHODS:
            raise InvalidPaymentMethodError(
                f"Payment method '{method}' is invalid. Supported methods: {sorted(ALLOWED_PAYMENT_METHODS)}"
            )

    @staticmethod
    def get_safe_fallback_customer(customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Provides a safe, conservative default customer context for missing customer profiles."""
        return {
            "customer_id": customer_id or "anonymous_customer",
            "preferred_payment_method": "UPI",
            "risk_score": 0.50,  # Conservative neutral risk
            "success_rate": 0.50,
            "total_transactions": 0,
            "failed_transactions": 0,
            "communication_opt_out": True,  # Conservative: do NOT send unverified messages
            "communication_allowed": False,
            "dnd": True,
            "is_fallback_profile": True,
        }
