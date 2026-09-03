from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.app.policy_engine import PolicyEngine, PolicyOutcome


class PaymentState(str, Enum):
    CREATED = "CREATED"
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


class PolicyBlockedExecutionError(PermissionError):
    """Raised when an action is blocked by the policy engine before reaching execution."""
    pass


class StatefulPaymentSimulator:
    """Realistic stateful payment simulator for sandbox experimentation. NO REAL PAYMENTS."""

    # Explicit state transition graph
    VALID_TRANSITIONS: Dict[PaymentState, List[PaymentState]] = {
        PaymentState.CREATED: [PaymentState.INITIATED, PaymentState.CANCELLED],
        PaymentState.INITIATED: [PaymentState.PROCESSING, PaymentState.FAILED, PaymentState.CANCELLED],
        PaymentState.PROCESSING: [PaymentState.SUCCESS, PaymentState.FAILED, PaymentState.PENDING],
        PaymentState.PENDING: [PaymentState.SUCCESS, PaymentState.FAILED, PaymentState.CANCELLED],
        PaymentState.FAILED: [PaymentState.INITIATED, PaymentState.PROCESSING, PaymentState.CANCELLED],
        PaymentState.SUCCESS: [PaymentState.REFUNDED],
        PaymentState.CANCELLED: [],  # Terminal
        PaymentState.REFUNDED: [],   # Terminal
    }

    def __init__(self, seed: Optional[int] = 42, policy_engine: Optional[PolicyEngine] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.policy_engine = policy_engine or PolicyEngine()
        self.payments: Dict[str, Dict[str, Any]] = {}
        self.events: List[Dict[str, Any]] = []
        self.idempotency_keys: Dict[str, str] = {}  # idempotency_key -> transaction_id
        self.scheduled_jobs: List[Dict[str, Any]] = []

    def _record_event(
        self,
        transaction_id: str,
        event_type: str,
        from_state: Optional[PaymentState],
        to_state: Optional[PaymentState],
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Records an event with complete state transition audit and explicit simulated labeling."""
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "transaction_id": transaction_id,
            "event_type": event_type,
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value if to_state else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
            "simulated": True,
            "environment": "SIMULATED_GATEWAY_SANDBOX",
        }
        self.events.append(event)
        return event

    def _transition(
        self,
        payment: Dict[str, Any],
        target_state: PaymentState,
        reason: str = "",
    ) -> None:
        """Validates and executes a state transition."""
        current_state = PaymentState(payment["status"])
        allowed_targets = self.VALID_TRANSITIONS.get(current_state, [])

        if target_state not in allowed_targets:
            raise InvalidStateTransitionError(
                f"Invalid state transition: Cannot transition payment '{payment['transaction_id']}' "
                f"from '{current_state.value}' to '{target_state.value}'. Allowed: {[s.value for s in allowed_targets]}"
            )

        payment["status"] = target_state.value
        payment["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._record_event(
            transaction_id=payment["transaction_id"],
            event_type="STATE_TRANSITION",
            from_state=current_state,
            to_state=target_state,
            details={"reason": reason},
        )

    def create_payment(
        self,
        amount: float,
        currency: str = "INR",
        customer_id: str = "cust_demo",
        merchant_id: str = "merch_demo",
        payment_method: str = "UPI",
        gateway: str = "GATEWAY_A",
        idempotency_key: Optional[str] = None,
        failure_code: Optional[str] = None,
        risk_score: float = 0.05,
        metadata: Optional[Dict[str, Any]] = None,
        transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a new simulated payment, validating duplicates and policy checks."""
        # Check Duplicate Payment prevention (Rule 2)
        if idempotency_key:
            if idempotency_key in self.idempotency_keys:
                existing_id = self.idempotency_keys[idempotency_key]
                existing_txn = self.payments[existing_id]
                self._record_event(
                    transaction_id=existing_id,
                    event_type="DUPLICATE_PAYMENT_BLOCKED",
                    from_state=None,
                    to_state=None,
                    details={"idempotency_key": idempotency_key, "action": "STOP"},
                )
                return {
                    "transaction_id": existing_id,
                    "status": existing_txn["status"],
                    "error": "DUPLICATE_PAYMENT_PREVENTED",
                    "message": "Duplicate payment prevented by idempotency guardrail.",
                    "simulated": True,
                    "environment": "SIMULATED_GATEWAY_SANDBOX",
                }

        # Policy Pre-Execution Guard: High risk check (Rule 3)
        if risk_score > 0.85 or failure_code == "HIGH_RISK":
            self.policy_engine.log_denial_audit("POL-003", "CREATE_PAYMENT", "Execution blocked: High-risk payment cannot execute", "CRITICAL")
            raise PolicyBlockedExecutionError(
                "Execution blocked by policy: High fraud risk payment cannot reach execution (Rule: POL-003)"
            )

        transaction_id = transaction_id or f"txn_sim_{uuid.uuid4().hex[:12]}"

        if idempotency_key:
            self.idempotency_keys[idempotency_key] = transaction_id

        created_at = datetime.now(timezone.utc).isoformat()
        payment: Dict[str, Any] = {
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "merchant_id": merchant_id,
            "amount": float(amount),
            "currency": currency,
            "payment_method": payment_method.upper(),
            "gateway": gateway.upper(),
            "status": PaymentState.CREATED.value,
            "failure_code": failure_code,
            "risk_score": float(risk_score),
            "attempt_number": 1,
            "merchant_order_status": "PENDING",
            "idempotency_key": idempotency_key,
            "created_at": created_at,
            "updated_at": created_at,
            "simulated": True,
            "environment": "SIMULATED_GATEWAY_SANDBOX",
            "metadata": metadata or {},
        }

        self.payments[transaction_id] = payment
        self._record_event(transaction_id, "PAYMENT_CREATED", None, PaymentState.CREATED)

        # Transition: CREATED -> INITIATED -> PROCESSING
        self._transition(payment, PaymentState.INITIATED, "Payment initiated by customer")
        self._transition(payment, PaymentState.PROCESSING, f"Routing to {gateway}")

        # Resolve Outcome based on failure scenario or deterministic RNG
        if failure_code == "ORDER_CREATION_FAILED":
            # Realistic scenario: Payment succeeds, but merchant fulfillment/order creation fails
            self._transition(payment, PaymentState.SUCCESS, "Payment captured successfully at gateway")
            payment["merchant_order_status"] = "UNRESOLVED"
            payment["failure_code"] = "ORDER_CREATION_FAILED"
            payment["note"] = "Payment captured; merchant order creation unresolved"
        elif failure_code in {"GATEWAY_TIMEOUT", "INSUFFICIENT_FUNDS", "CARD_EXPIRED", "CUSTOMER_ABANDONED", "BANK_UNAVAILABLE"}:
            self._transition(payment, PaymentState.FAILED, f"Payment failed with code: {failure_code}")
            payment["failure_code"] = failure_code
        else:
            # Baseline simulation
            roll = self.rng.random()
            if roll < 0.85:
                self._transition(payment, PaymentState.SUCCESS, "Transaction authorized and captured")
                payment["merchant_order_status"] = "CONFIRMED"
            elif roll < 0.95:
                self._transition(payment, PaymentState.FAILED, "Card authorization declined")
                payment["failure_code"] = "CARD_DECLINED"
            else:
                self._transition(payment, PaymentState.PENDING, "Awaiting asynchronous banking settlement")

        return dict(payment)

    def retry_payment(self, transaction_id: str, delay_seconds: int = 0) -> Dict[str, Any]:
        """Retries a failed payment, modeling causal outcome based on failure type."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")

        # Policy Pre-Execution Guard
        prev_attempts = max(0, payment.get("attempt_number", 1) - 1)
        pol_check = self.policy_engine.evaluate({
            "action": "RETRY_PAYMENT",
            "status": payment["status"],
            "failure_code": payment.get("failure_code"),
            "risk_score": payment.get("risk_score", 0.0),
        }, previous_attempts=prev_attempts)


        if not pol_check.allowed:
            raise PolicyBlockedExecutionError(
                f"Execution blocked by policy: {pol_check.reason} (Rule: {pol_check.rule_id})"
            )

        # Transition: FAILED -> INITIATED -> PROCESSING
        self._transition(payment, PaymentState.INITIATED, "Retry payment requested")
        self._transition(payment, PaymentState.PROCESSING, "Dispatching retry to gateway")
        payment["attempt_number"] = payment.get("attempt_number", 1) + 1

        failure_code = payment.get("failure_code")
        payment_method = payment.get("payment_method")

        # Causal modeling
        if failure_code == "GATEWAY_TIMEOUT":
            # Temporary timeout: 82% success rate on retry
            success = self.rng.random() < 0.82
        elif failure_code == "CARD_EXPIRED":
            # Expired card: retrying same card always fails (0% success)
            success = False
        elif failure_code == "INSUFFICIENT_FUNDS":
            # Immediate retry on insufficient funds fails 92% of the time unless delay was introduced
            prob = 0.65 if delay_seconds >= 300 else 0.08
            success = self.rng.random() < prob
        elif failure_code == "CUSTOMER_ABANDONED":
            # Cannot retry an unauthenticated/abandoned session directly
            success = False
        else:
            success = self.rng.random() < 0.70

        if success:
            self._transition(payment, PaymentState.SUCCESS, "Retry authorization succeeded")
            payment["failure_code"] = None
        else:
            self._transition(payment, PaymentState.FAILED, f"Retry failed on {payment_method}")

        return dict(payment)

    def switch_payment_method(self, transaction_id: str, new_payment_method: str) -> Dict[str, Any]:
        """Switches payment instrument and attempts payment recovery."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")

        # Pre-execution policy check
        pol_check = self.policy_engine.evaluate({
            "action": "SWITCH_PAYMENT_METHOD",
            "status": payment["status"],
            "risk_score": payment.get("risk_score", 0.0),
        })
        if not pol_check.allowed:
            raise PolicyBlockedExecutionError(
                f"Execution blocked by policy: {pol_check.reason} (Rule: {pol_check.rule_id})"
            )

        old_method = payment["payment_method"]
        payment["payment_method"] = new_payment_method.upper()
        payment["attempt_number"] = payment.get("attempt_number", 1) + 1

        self._record_event(
            transaction_id,
            "PAYMENT_METHOD_SWITCHED",
            PaymentState(payment["status"]),
            None,
            details={"old_method": old_method, "new_method": new_payment_method.upper()},
        )

        self._transition(payment, PaymentState.INITIATED, f"Initiating payment via {new_payment_method.upper()}")
        self._transition(payment, PaymentState.PROCESSING, f"Processing on {new_payment_method.upper()}")

        # Switching from an expired or declined card to UPI / alternate instrument has high recovery (85%)
        success = self.rng.random() < 0.85
        if success:
            self._transition(payment, PaymentState.SUCCESS, f"Payment successfully recovered via {new_payment_method.upper()}")
            payment["failure_code"] = None
        else:
            self._transition(payment, PaymentState.FAILED, f"Payment failed on {new_payment_method.upper()}")

        return dict(payment)

    def send_recovery_message(self, transaction_id: str, channel: str = "WHATSAPP") -> Dict[str, Any]:
        """Sends a recovery reminder (SMS/WhatsApp). For abandoned checkouts, models customer return."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")

        self._record_event(
            transaction_id,
            "RECOVERY_MESSAGE_SENT",
            PaymentState(payment["status"]),
            None,
            details={"channel": channel.upper()},
        )

        # Abandoned checkout causal model: message causes customer return (70% conversion)
        customer_returned = False
        if payment.get("failure_code") == "CUSTOMER_ABANDONED":
            customer_returned = self.rng.random() < 0.70

            if customer_returned:
                self._record_event(
                    transaction_id,
                    "CUSTOMER_RETURNED_FROM_MESSAGE",
                    PaymentState(payment["status"]),
                    None,
                    details={"channel": channel.upper()},
                )
                self._transition(payment, PaymentState.INITIATED, "Customer returned via recovery message link")
                self._transition(payment, PaymentState.PROCESSING, "Customer authorized checkout")
                self._transition(payment, PaymentState.SUCCESS, "Checkout completed successfully")
                payment["failure_code"] = None

        return {
            "transaction_id": transaction_id,
            "message_sent": True,
            "channel": channel.upper(),
            "customer_returned": customer_returned,
            "current_status": payment["status"],
            "simulated": True,
            "environment": "SIMULATED_GATEWAY_SANDBOX",
        }

    def schedule_retry(self, transaction_id: str, delay_seconds: int = 300) -> Dict[str, Any]:
        """Schedules a future retry and records job in simulator."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")

        job_id = f"job_sim_{uuid.uuid4().hex[:8]}"
        job = {
            "job_id": job_id,
            "transaction_id": transaction_id,
            "delay_seconds": delay_seconds,
            "status": "SCHEDULED",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
        self.scheduled_jobs.append(job)

        self._record_event(
            transaction_id,
            "RETRY_SCHEDULED",
            PaymentState(payment["status"]),
            None,
            details={"job_id": job_id, "delay_seconds": delay_seconds},
        )

        return {
            "job_id": job_id,
            "transaction_id": transaction_id,
            "status": "SCHEDULED",
            "delay_seconds": delay_seconds,
            "simulated": True,
            "environment": "SIMULATED_GATEWAY_SANDBOX",
        }

    def get_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """Retrieves payment state, attempt number, and full event log."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")

        related_events = [e for e in self.events if e["transaction_id"] == transaction_id]

        return {
            "payment": dict(payment),
            "status": payment["status"],
            "events_count": len(related_events),
            "events": related_events,
            "simulated": True,
            "environment": "SIMULATED_GATEWAY_SANDBOX",
        }

    def refund_payment(self, transaction_id: str, reason: str = "Customer requested refund") -> Dict[str, Any]:
        """Simulates refunding a previously successful payment."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")
        self._transition(payment, PaymentState.REFUNDED, reason=reason)
        return dict(payment)

    def cancel_payment(self, transaction_id: str, reason: str = "Payment session cancelled") -> Dict[str, Any]:
        """Simulates cancelling a payment."""
        payment = self.payments.get(transaction_id)
        if not payment:
            raise KeyError(f"Transaction '{transaction_id}' not found in simulator.")
        self._transition(payment, PaymentState.CANCELLED, reason=reason)
        return dict(payment)


PaymentSimulator = StatefulPaymentSimulator


