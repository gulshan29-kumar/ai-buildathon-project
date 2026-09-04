from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.app.failure_classifier import (
    FailureCategory,
    FailureClassification,
    FailureClassifier,
)


class PolicyOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    WAIT = "WAIT"
    ESCALATE = "ESCALATE"


class PolicySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class PolicyRule:
    rule_id: str
    name: str
    description: str
    severity: PolicySeverity


@dataclass
class PolicyDecision:
    outcome: PolicyOutcome
    allowed: bool
    rule_id: str
    reason: str
    severity: str
    action: Optional[str] = None
    classification: Optional[FailureClassification] = None
    audit_logged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "allowed": self.allowed,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "severity": self.severity,
            "action": self.action,
            "audit_logged": self.audit_logged,
            "metadata": self.metadata,
        }


class PolicyEngine:
    """Deterministic Policy and Safety Engine enforcing all 12 platform guardrails."""

    RULES = {
        "POL-001": PolicyRule("POL-001", "Never Retry Success", "Never retry an already successful transaction", PolicySeverity.CRITICAL),
        "POL-002": PolicyRule("POL-002", "Never Retry Duplicate", "Never retry duplicate payments", PolicySeverity.CRITICAL),
        "POL-003": PolicyRule("POL-003", "Block High-Risk Auto-Recovery", "Never automatically recover high-risk/fraud transactions", PolicySeverity.CRITICAL),
        "POL-004": PolicyRule("POL-004", "Enforce Retry Limits", "Enforce maximum attempt limits per action", PolicySeverity.HIGH),
        "POL-005": PolicyRule("POL-005", "Enforce Retry Cooldown", "Enforce minimum cooldown interval between retries", PolicySeverity.MEDIUM),
        "POL-006": PolicyRule("POL-006", "Escalate High-Value Risky", "High-value risky payments must escalate to manual review", PolicySeverity.HIGH),
        "POL-007": PolicyRule("POL-007", "Wait for Pending Payments", "Pending payments must wait instead of retrying", PolicySeverity.HIGH),
        "POL-008": PolicyRule("POL-008", "Stop on Invalid State", "Invalid payment state must halt execution", PolicySeverity.CRITICAL),
        "POL-009": PolicyRule("POL-009", "Respect Communication Permissions", "Customer messaging must respect communication permissions and DND", PolicySeverity.MEDIUM),
        "POL-010": PolicyRule("POL-010", "Audit Every Denial", "Every denied action must be logged in the audit registry", PolicySeverity.HIGH),
        "POL-011": PolicyRule("POL-011", "LLM Cannot Bypass Policy", "External or LLM suggestions cannot override deterministic policy rules", PolicySeverity.CRITICAL),
        "POL-012": PolicyRule("POL-012", "Pre-Execution Gate", "Policy evaluation strictly runs before any payment execution", PolicySeverity.CRITICAL),
    }

    def __init__(self):
        self.retry_limits = {"RETRY_PAYMENT": 2, "SCHEDULE_RETRY": 3, "SWITCH_PAYMENT_METHOD": 2}
        self.cooldown_seconds = {"RETRY_PAYMENT": 60, "SCHEDULE_RETRY": 300}
        self.high_value_threshold = 50000.0  # ₹50,000
        self.risky_score_threshold = 0.50
        self.critical_fraud_threshold = 0.85
        self.audit_records: List[Dict[str, Any]] = []

    def log_denial_audit(
        self,
        rule_id: str,
        action: Optional[str],
        reason: str,
        severity: str,
        transaction_id: Optional[str] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Rule 10 (POL-010): Every denied action must be audited."""
        audit_entry = {
            "event_type": "POLICY_DENIAL",
            "rule_id": rule_id,
            "action": action,
            "transaction_id": transaction_id or "unknown",
            "reason": reason,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": event_metadata or {},
        }
        self.audit_records.append(audit_entry)

        try:
            from backend.app.audit_trail import AuditTrail
            AuditTrail.get_instance().log_event(
                transaction_id=transaction_id or "unknown",
                event_type="POLICY_CHECKED",
                actor="POLICY_ENGINE",
                selected_action=action,
                policy_result="DENY",
                policy_rule=rule_id,
                input_summary={"severity": severity, "reason": reason, "metadata": event_metadata or {}},
            )
        except Exception:
            pass

        return True


    def evaluate(
        self,
        event: Dict[str, Any],
        customer_context: Optional[Dict[str, Any]] = None,
        previous_attempts: int = 0,
        customer_risk: float = 0.0,
        last_attempt_timestamp: Optional[datetime] = None,
    ) -> PolicyDecision:
        """Evaluates all policy rules before action execution."""
        # Rule 12 (POL-012): Runs strictly before execution
        txn_id = str(event.get("transaction_id", "txn_unknown"))
        raw_status = str(event.get("status", "")).upper()
        failure_type = str(event.get("failure_type") or event.get("failure_code") or "").upper()
        action = str(event.get("recommended_action") or event.get("action") or "RETRY_PAYMENT").upper()
        amount = float(event.get("amount", 0.0))
        risk_score = max(customer_risk, float(event.get("risk_score", 0.0)))

        # Resolve classification
        classification = FailureClassifier.classify(failure_type) if failure_type else None

        # Rule 11 (POL-011): LLM/override bypass protection
        notes_str = str(event.get("notes", "")).lower()
        prompt_str = str(event.get("prompt", "") or event.get("instructions", "")).lower()
        has_prompt_injection = any(
            phrase in notes_str or phrase in prompt_str
            for phrase in ["ignore all prior", "bypass guardrails", "ignore policy", "override policy", "jailbreak", "override guardrails"]
        )
        if (
            event.get("llm_override")
            or event.get("bypass_guardrails")
            or event.get("force_bypass")
            or event.get("force_retry")
            or event.get("override_policy")
            or has_prompt_injection
        ):
            self.log_denial_audit("POL-011", action, "Bypass attempt rejected: LLM and external overrides cannot bypass safety policy", PolicySeverity.CRITICAL.value, txn_id)
            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                allowed=False,
                rule_id="POL-011",
                reason="Bypass attempt rejected: LLM and external overrides cannot bypass safety policy.",
                severity=PolicySeverity.CRITICAL.value,
                action="STOP",
                classification=classification,
                audit_logged=True,
            )


        # Rule 1 (POL-001): Never retry a successful transaction
        if raw_status == "SUCCESS":
            self.log_denial_audit("POL-001", action, "Cannot execute recovery on an already successful transaction", PolicySeverity.CRITICAL.value, txn_id)
            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                allowed=False,
                rule_id="POL-001",
                reason="Blocked by safety policy: Transaction is already successful. Further payment action prohibited.",
                severity=PolicySeverity.CRITICAL.value,
                action="STOP",
                classification=classification,
                audit_logged=True,
            )

        # Rule 2 (POL-002): Never retry duplicate payments
        if failure_type == "DUPLICATE_PAYMENT" or (classification and classification.category == FailureCategory.DUPLICATE):
            self.log_denial_audit("POL-002", action, "Duplicate payment detected. Execution halted", PolicySeverity.CRITICAL.value, txn_id)
            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                allowed=False,
                rule_id="POL-002",
                reason="Blocked by safety policy: Duplicate payment detected. Execution halted.",
                severity=PolicySeverity.CRITICAL.value,
                action="STOP",
                classification=classification,
                audit_logged=True,
            )

        # Rule 8 (POL-008): Invalid payment state should stop
        valid_states = {"CREATED", "INITIATED", "PROCESSING", "FAILED", "PENDING", "CANCELLED", "REFUNDED", "ABANDONED", ""}
        if raw_status and raw_status not in valid_states:
            self.log_denial_audit("POL-008", action, f"Corrupted or invalid payment state: '{raw_status}'", PolicySeverity.CRITICAL.value, txn_id)
            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                allowed=False,
                rule_id="POL-008",
                reason=f"Blocked by safety policy: Invalid payment state '{raw_status}'. Action terminated.",
                severity=PolicySeverity.CRITICAL.value,
                action="STOP",
                classification=classification,
                audit_logged=True,
            )

        # Rule 3 (POL-003): Never automatically recover high-risk/fraud transactions
        if risk_score > self.critical_fraud_threshold or (classification and classification.category == FailureCategory.RISK):
            if action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD", "SCHEDULE_RETRY", "SEND_RECOVERY_MESSAGE"}:
                self.log_denial_audit("POL-003", action, f"High fraud risk ({risk_score:.2f}). Automated recovery prohibited", PolicySeverity.CRITICAL.value, txn_id)
                return PolicyDecision(
                    outcome=PolicyOutcome.ESCALATE,
                    allowed=False,
                    rule_id="POL-003",
                    reason=f"Blocked by safety policy: Fraud risk score ({risk_score:.2f}) exceeds critical safety threshold. Must escalate to risk operations.",
                    severity=PolicySeverity.CRITICAL.value,
                    action="ESCALATE",
                    classification=classification,
                    audit_logged=True,
                )

        # Rule 6 (POL-006): High-value risky payments should escalate
        if amount >= self.high_value_threshold and risk_score >= self.risky_score_threshold:
            if action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
                self.log_denial_audit("POL-006", action, f"High-value payment (₹{amount:,.2f}) with elevated risk ({risk_score:.2f}) requires human review", PolicySeverity.HIGH.value, txn_id)
                return PolicyDecision(
                    outcome=PolicyOutcome.ESCALATE,
                    allowed=False,
                    rule_id="POL-006",
                    reason=f"Policy requirement: High-value transaction (₹{amount:,.2f}) with elevated risk score ({risk_score:.2f}) must escalate to human review.",
                    severity=PolicySeverity.HIGH.value,
                    action="ESCALATE",
                    classification=classification,
                    audit_logged=True,
                )

        # Rule 7 (POL-007): Pending payments should wait
        if raw_status == "PENDING" or failure_type == "PAYMENT_PENDING" or (classification and classification.category == FailureCategory.PENDING):
            if action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
                return PolicyDecision(
                    outcome=PolicyOutcome.WAIT,
                    allowed=False,
                    rule_id="POL-007",
                    reason="Policy requirement: Payment is pending settlement with gateway/bank. Wait and poll status instead of retrying.",
                    severity=PolicySeverity.HIGH.value,
                    action="WAIT_AND_POLL",
                    classification=classification,
                    audit_logged=False,
                )

        # Specific failure code constraint: Expired card cannot be retried
        if failure_type == "CARD_EXPIRED" and action == "RETRY_PAYMENT":
            self.log_denial_audit("POL-003", action, "Cannot retry on an expired card", PolicySeverity.HIGH.value, txn_id)
            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                allowed=False,
                rule_id="POL-003",
                reason="Blocked by safety policy: Cannot retry on an expired card. Switch payment method required.",
                severity=PolicySeverity.HIGH.value,
                action="SWITCH_PAYMENT_METHOD",
                classification=classification,
                audit_logged=True,
            )

        # Rule 4 (POL-004): Enforce retry limits
        max_allowed_attempts = self.retry_limits.get(action, 2)
        if previous_attempts >= max_allowed_attempts and action in {"RETRY_PAYMENT", "SCHEDULE_RETRY"}:
            self.log_denial_audit("POL-004", action, f"Retry limit ({max_allowed_attempts}) reached for {action}", PolicySeverity.HIGH.value, txn_id)

            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                allowed=False,
                rule_id="POL-004",
                reason=f"Blocked by safety policy: Maximum retry limit ({max_allowed_attempts}) exceeded for action '{action}'.",
                severity=PolicySeverity.HIGH.value,
                action="ESCALATE" if previous_attempts >= 3 else "STOP",
                classification=classification,
                audit_logged=True,
            )

        # Rule 5 (POL-005): Enforce retry cooldown
        if last_attempt_timestamp and action in self.cooldown_seconds:
            cooldown = self.cooldown_seconds[action]
            now = datetime.now(timezone.utc)
            if last_attempt_timestamp.tzinfo is None:
                last_attempt_timestamp = last_attempt_timestamp.replace(tzinfo=timezone.utc)
            elapsed = (now - last_attempt_timestamp).total_seconds()
            if elapsed < cooldown:
                return PolicyDecision(
                    outcome=PolicyOutcome.WAIT,
                    allowed=False,
                    rule_id="POL-005",
                    reason=f"Policy requirement: Minimum cooldown period ({cooldown}s) active. {int(cooldown - elapsed)}s remaining.",
                    severity=PolicySeverity.MEDIUM.value,
                    action="WAIT",
                    classification=classification,
                    audit_logged=False,
                )

        # Rule 9 (POL-009): Customer communication must respect permissions
        if action == "SEND_RECOVERY_MESSAGE":
            cust = customer_context or event.get("customer_context") or {}
            opt_out = cust.get("communication_opt_out", False) or cust.get("opt_out", False) or event.get("communication_opt_out", False) or event.get("opt_out", False)
            dnd = cust.get("dnd", False) or cust.get("do_not_disturb", False) or event.get("dnd", False) or event.get("dnd_enabled", False)
            communication_allowed = cust.get("communication_allowed", True) and event.get("communication_allowed", True)

            if opt_out or dnd or not communication_allowed:
                self.log_denial_audit("POL-009", action, "Customer opted out or DND active", PolicySeverity.MEDIUM.value, txn_id)
                return PolicyDecision(
                    outcome=PolicyOutcome.DENY,
                    allowed=False,
                    rule_id="POL-009",
                    reason="Blocked by safety policy: Customer has opted out of notifications or has active Do-Not-Disturb (DND).",
                    severity=PolicySeverity.MEDIUM.value,
                    action="STOP",
                    classification=classification,
                    audit_logged=True,
                )

        # Default: All policy checks passed
        return PolicyDecision(
            outcome=PolicyOutcome.ALLOW,
            allowed=True,
            rule_id="POL-000",
            reason="Action permitted under deterministic policy rules.",
            severity=PolicySeverity.LOW.value,
            action=action,
            classification=classification,
            audit_logged=False,
        )
