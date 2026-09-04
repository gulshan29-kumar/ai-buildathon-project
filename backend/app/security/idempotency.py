from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("backend.app.security.idempotency")


class IdempotencyConflictError(Exception):
    """Raised when an idempotent request with the same key is currently being processed (HTTP 409)."""
    pass


class IdempotencyMismatchError(Exception):
    """Raised when an idempotency key is reused with a different request payload (HTTP 422)."""
    pass


class ReplayAttackDetectedError(Exception):
    """Raised when a stale or duplicated payment/webhook event is detected."""
    pass


class IdempotencyRecord:
    """Represents a cached response or in-flight lock for an idempotency key."""

    def __init__(self, key: str, request_hash: str, ttl_seconds: int = 86400):
        self.key = key
        self.request_hash = request_hash
        self.status = "IN_PROGRESS"  # IN_PROGRESS | COMPLETED
        self.response_code: int = 200
        self.response_body: Any = None
        self.created_at = time.time()
        self.ttl = ttl_seconds

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


class IdempotencyManager:
    """Thread-safe In-Memory Idempotency Store with Replay Attack & Duplicate Protection."""

    _instance: Optional[IdempotencyManager] = None
    _lock = threading.Lock()

    def __init__(self, default_ttl: int = 86400):
        self.records: Dict[str, IdempotencyRecord] = {}
        self.event_hashes: Dict[str, float] = {}  # event_hash -> timestamp
        self.default_ttl = default_ttl
        self._mutex = threading.Lock()

    @classmethod
    def get_instance(cls) -> IdempotencyManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @staticmethod
    def compute_hash(data: Any) -> str:
        """Generates a deterministic SHA-256 hash of the payload."""
        if isinstance(data, (dict, list)):
            canonical = json.dumps(data, sort_keys=True, default=str)
        else:
            canonical = str(data or "")
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def start_request(
        self,
        key: str,
        payload_or_hash: Any,
        ttl_seconds: Optional[int] = None,
    ) -> Optional[Tuple[int, Any]]:
        """Checks for existing idempotency records or marks request IN_PROGRESS.
        
        Returns:
            (status_code, cached_body) if already COMPLETED.
            None if new and successfully locked.
            
        Raises:
            IdempotencyConflictError: If currently IN_PROGRESS.
            IdempotencyMismatchError: If key was previously used with a different payload.
        """
        if not key:
            return None

        req_hash = (
            payload_or_hash
            if isinstance(payload_or_hash, str) and len(payload_or_hash) == 64
            else self.compute_hash(payload_or_hash)
        )
        ttl = ttl_seconds or self.default_ttl

        with self._mutex:
            record = self.records.get(key)

            if record:
                # If expired, remove and restart
                if record.is_expired():
                    del self.records[key]
                    record = None
                elif record.request_hash != req_hash:
                    logger.warning(
                        f"[SECURITY ALERT] Idempotency key '{key}' payload mismatch. "
                        f"Expected hash {record.request_hash}, received {req_hash}."
                    )
                    raise IdempotencyMismatchError(
                        f"Idempotency key '{key}' was previously used with a different request payload."
                    )
                elif record.status == "IN_PROGRESS":
                    # Concurrent request with same key
                    raise IdempotencyConflictError(
                        f"Request with idempotency key '{key}' is currently being processed."
                    )
                elif record.status == "COMPLETED":
                    logger.info(f"Idempotency cache HIT for key '{key}' (Code: {record.response_code})")
                    return record.response_code, record.response_body

            # Brand new key: set lock
            self.records[key] = IdempotencyRecord(key, req_hash, ttl_seconds=ttl)
            return None

    def complete_request(self, key: str, status_code: int, response_body: Any) -> None:
        """Caches the completed response for an idempotency key."""
        if not key:
            return
        with self._mutex:
            record = self.records.get(key)
            if record:
                record.status = "COMPLETED"
                record.response_code = status_code
                record.response_body = response_body

    def fail_request(self, key: str) -> None:
        """Removes an IN_PROGRESS lock if the request failed with an unexpected error."""
        if not key:
            return
        with self._mutex:
            record = self.records.get(key)
            if record and record.status == "IN_PROGRESS":
                del self.records[key]

    # --- Duplicate Event & Replay Attack Protection ---

    def verify_and_record_event(
        self,
        event_id: str,
        transaction_id: str,
        event_type: str,
        timestamp_epoch: Optional[float] = None,
        max_age_seconds: int = 300,
    ) -> None:
        """Detects duplicate events and replay attacks on webhook/payment events.
        
        Raises ReplayAttackDetectedError if the event is a duplicate or too old.
        """
        now = time.time()

        # 1. Freshness check: Reject events older than max_age_seconds (if timestamp provided)
        if timestamp_epoch is not None:
            if abs(now - timestamp_epoch) > max_age_seconds:
                raise ReplayAttackDetectedError(
                    f"Replay attack detected: Event timestamp is outside the allowed {max_age_seconds}s window."
                )

        # 2. Duplicate fingerprinting
        fingerprint = f"{event_id}:{transaction_id}:{event_type}"
        with self._mutex:
            if fingerprint in self.event_hashes:
                prev_time = self.event_hashes[fingerprint]
                if (now - prev_time) < max_age_seconds:
                    logger.warning(f"[SECURITY ALERT] Duplicate event replayed: '{fingerprint}'")
                    raise ReplayAttackDetectedError(
                        f"Duplicate event detected: Event '{event_id}' has already been processed."
                    )
            self.event_hashes[fingerprint] = now

            # Clean old event hashes occasionally
            if len(self.event_hashes) > 10000:
                cutoff = now - max_age_seconds
                self.event_hashes = {k: v for k, v in self.event_hashes.items() if v > cutoff}


def get_idempotency_manager() -> IdempotencyManager:
    return IdempotencyManager.get_instance()
