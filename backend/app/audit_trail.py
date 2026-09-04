from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    """Immutable-style audit record capturing platform actions with tamper-evident hash chaining."""

    audit_id: str
    transaction_id: str
    timestamp: str
    event_type: str
    actor: str
    input_summary: Dict[str, Any] = field(default_factory=dict)
    root_cause: Optional[Dict[str, Any] | str] = None
    recovery_probability: Optional[float] = None
    candidate_actions: Optional[List[Dict[str, Any]]] = None
    selected_action: Optional[str] = None
    expected_value: Optional[float] = None
    policy_result: Optional[str] = None
    policy_rule: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    revenue_recovered: Optional[float] = None
    model_version: str = "v1.2.0"
    agent_version: str = "v1.0.0"
    previous_hash: Optional[str] = None
    hash: str = ""

    def compute_hash(self) -> str:
        """Computes cryptographic SHA-256 digest of record contents to establish tamper-evidence."""
        content = {
            "audit_id": self.audit_id,
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "selected_action": self.selected_action,
            "policy_result": self.policy_result,
            "policy_rule": self.policy_rule,
            "revenue_recovered": self.revenue_recovered,
            "previous_hash": self.previous_hash or "GENESIS",
        }
        raw_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


class AuditTrail:
    """Append-only, immutable-style audit registry with cryptographic verification."""

    _instance: Optional[AuditTrail] = None

    def __init__(self):
        self._events: List[AuditEvent] = []
        self._by_transaction: Dict[str, List[AuditEvent]] = {}
        self._last_hash_by_transaction: Dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> AuditTrail:
        if cls._instance is None:
            cls._instance = AuditTrail()
        return cls._instance

    def log_event(
        self,
        transaction_id: str,
        event_type: str,
        actor: str = "ORCHESTRATOR",
        input_summary: Optional[Dict[str, Any]] = None,
        root_cause: Optional[Dict[str, Any] | str] = None,
        recovery_probability: Optional[float] = None,
        candidate_actions: Optional[List[Dict[str, Any]]] = None,
        selected_action: Optional[str] = None,
        expected_value: Optional[float] = None,
        policy_result: Optional[str] = None,
        policy_rule: Optional[str] = None,
        execution_result: Optional[Dict[str, Any]] = None,
        revenue_recovered: Optional[float] = None,
        model_version: str = "v1.2.0",
        agent_version: str = "v1.0.0",
        timestamp: Optional[str] = None,
    ) -> AuditEvent:
        """Appends an immutable audit event for a transaction."""
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        prev_hash = self._last_hash_by_transaction.get(transaction_id)

        event = AuditEvent(
            audit_id=audit_id,
            transaction_id=transaction_id,
            timestamp=ts,
            event_type=event_type,
            actor=actor,
            input_summary=input_summary or {},
            root_cause=root_cause,
            recovery_probability=recovery_probability,
            candidate_actions=candidate_actions,
            selected_action=selected_action,
            expected_value=expected_value,
            policy_result=policy_result,
            policy_rule=policy_rule,
            execution_result=execution_result,
            revenue_recovered=revenue_recovered,
            model_version=model_version,
            agent_version=agent_version,
            previous_hash=prev_hash,
        )
        event.hash = event.compute_hash()

        self._events.append(event)
        if transaction_id not in self._by_transaction:
            self._by_transaction[transaction_id] = []
        self._by_transaction[transaction_id].append(event)
        self._last_hash_by_transaction[transaction_id] = event.hash

        return event

    def get_timeline(self, transaction_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological timeline of audit events for a transaction."""
        events = self._by_transaction.get(transaction_id, [])
        # Ensure chronological ordering by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        return [e.to_dict() for e in sorted_events]

    def verify_integrity(self, transaction_id: str) -> bool:
        """Verifies cryptographic chain integrity for a transaction's audit timeline."""
        events = self._by_transaction.get(transaction_id, [])
        if not events:
            return True

        expected_prev_hash: Optional[str] = None
        for evt in events:
            if evt.previous_hash != expected_prev_hash:
                logger.error(f"Audit chain broken at event {evt.audit_id}: previous hash mismatch.")
                return False
            recomputed = evt.compute_hash()
            if evt.hash != recomputed:
                logger.error(f"Audit record altered at event {evt.audit_id}: content hash mismatch.")
                return False
            expected_prev_hash = evt.hash

        return True

    def get_all_events(
        self,
        transaction_id: Optional[str] = None,
        actor: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Retrieves paginated audit events across all transactions with filtering."""
        filtered = self._events
        if transaction_id:
            filtered = [e for e in filtered if e.transaction_id == transaction_id]
        if actor:
            filtered = [e for e in filtered if e.actor.upper() == actor.upper()]
        if event_type:
            filtered = [e for e in filtered if e.event_type.upper() == event_type.upper()]

        # Sort descending by timestamp
        sorted_events = sorted(filtered, key=lambda e: e.timestamp, reverse=True)
        paged = sorted_events[offset : offset + limit]
        actors = sorted(list({e.actor for e in self._events}))

        return {
            "total": len(sorted_events),
            "limit": limit,
            "offset": offset,
            "actors": actors,
            "events": [e.to_dict() for e in paged],
        }

    def verify_all_integrity(self) -> bool:
        """Verifies cryptographic integrity across every transaction chain."""
        for tx_id in self._by_transaction:
            if not self.verify_integrity(tx_id):
                return False
        return True

    def clear(self) -> None:
        """Resets the audit registry (primarily for test isolation)."""
        self._events.clear()
        self._by_transaction.clear()
        self._last_hash_by_transaction.clear()
