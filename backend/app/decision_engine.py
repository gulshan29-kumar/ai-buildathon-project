from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.action_predictor import (
    SUPPORTED_ACTIONS,
    ActionRecoveryPredictor,
)
from backend.app.failure_classifier import FailureCategory, FailureClassifier
from backend.app.policy_engine import PolicyDecision, PolicyEngine, PolicyOutcome


ACTION_PRIORITY = [
    "RETRY_PAYMENT",
    "SWITCH_PAYMENT_METHOD",
    "SCHEDULE_RETRY",
    "SEND_RECOVERY_MESSAGE",
    "ESCALATE",
    "STOP",
]


@dataclass
class RecoveryCandidate:
    action: str
    probability: float
    expected_recovery_value: float
    permitted: bool
    policy_outcome: str
    rule_id: str
    rejection_reason: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "probability": self.probability,
            "expected_recovery_value": self.expected_recovery_value,
            "permitted": self.permitted,
            "policy_outcome": self.policy_outcome,
            "rule_id": self.rule_id,
            "rejection_reason": self.rejection_reason,
            "parameters": self.parameters,
        }


@dataclass
class RecoveryDecision:
    transaction_id: str
    selected_action: str
    recovery_probability: float
    expected_recovery_value: float
    reasoning_summary: str
    policy_status: str
    candidates: List[RecoveryCandidate]
    fallback_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "selected_action": self.selected_action,
            "recovery_probability": self.recovery_probability,
            "expected_recovery_value": self.expected_recovery_value,
            "reasoning_summary": self.reasoning_summary,
            "policy_status": self.policy_status,
            "candidates": [c.to_dict() for c in self.candidates],
            "fallback_action": self.fallback_action,
            "metadata": self.metadata,
        }


class DecisionEngine:
    """Deterministic Recovery Decision Engine without any LLM dependency."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        action_predictor: Optional[ActionRecoveryPredictor] = None,
    ):
        self.policy_engine = policy_engine or PolicyEngine()
        self.action_predictor = action_predictor or ActionRecoveryPredictor()

    def decide(
        self,
        transaction: Optional[Dict[str, Any]] = None,
        customer_context: Optional[Dict[str, Any]] = None,
        payment_context: Optional[Dict[str, Any]] = None,
        action_probabilities: Optional[Dict[str, float]] = None,
        available_payment_methods: Optional[List[str]] = None,
    ) -> RecoveryDecision:
        """Evaluates candidates, ranks by expected value, handles edge cases, and chooses best permitted action."""
        # Handle Edge Case 9: Missing or empty context
        txn = dict(transaction or {})
        cust = dict(customer_context or {})
        pay_ctx = dict(payment_context or {})

        txn_id = str(txn.get("transaction_id") or txn.get("id") or "txn_unknown")
        amount = max(0.0, float(txn.get("amount", 0.0)))
        status = str(txn.get("status", "FAILED")).upper()
        failure_code = str(txn.get("failure_code") or txn.get("failure_type") or "").upper()
        risk_score = max(0.0, float(txn.get("risk_score") or cust.get("risk_score", 0.05)))
        current_method = str(txn.get("payment_method") or "UPI").upper()
        previous_attempts = int(txn.get("attempt_number", 1)) - 1
        if previous_attempts < 0:
            previous_attempts = int(txn.get("previous_attempts", 0))

        classification = FailureClassifier.classify(failure_code) if failure_code else None

        # Edge Case 1: Already successful
        if status == "SUCCESS":
            stop_candidate = RecoveryCandidate(
                action="STOP",
                probability=0.0,
                expected_recovery_value=0.0,
                permitted=True,
                policy_outcome="ALLOW",
                rule_id="POL-001",
                rejection_reason=None,
            )
            return RecoveryDecision(
                transaction_id=txn_id,
                selected_action="STOP",
                recovery_probability=0.0,
                expected_recovery_value=0.0,
                reasoning_summary="Transaction is already successful. Further recovery action halted.",
                policy_status="HALTED",
                candidates=[stop_candidate],
                metadata={"status": status},
            )

        # Edge Case 2: Pending payment
        if status == "PENDING" or failure_code == "PAYMENT_PENDING" or (classification and classification.category == FailureCategory.PENDING):
            wait_candidate = RecoveryCandidate(
                action="WAIT_AND_POLL",
                probability=0.0,
                expected_recovery_value=0.0,
                permitted=True,
                policy_outcome="WAIT",
                rule_id="POL-007",
                parameters={"poll_interval_seconds": 30},
            )
            return RecoveryDecision(
                transaction_id=txn_id,
                selected_action="WAIT_AND_POLL",
                recovery_probability=0.0,
                expected_recovery_value=0.0,
                reasoning_summary="Payment is pending settlement with gateway. Deferring execution to poll status.",
                policy_status="WAIT",
                candidates=[wait_candidate],
                metadata={"status": "PENDING"},
            )

        # Edge Case 3: Duplicate payment
        if failure_code == "DUPLICATE_PAYMENT" or (classification and classification.category == FailureCategory.DUPLICATE):
            stop_candidate = RecoveryCandidate(
                action="STOP",
                probability=0.0,
                expected_recovery_value=0.0,
                permitted=True,
                policy_outcome="DENY",
                rule_id="POL-002",
                rejection_reason="Duplicate payment detected. Execution halted to prevent double charge.",
            )
            return RecoveryDecision(
                transaction_id=txn_id,
                selected_action="STOP",
                recovery_probability=0.0,
                expected_recovery_value=0.0,
                reasoning_summary="Duplicate payment detected. Execution halted by safety guardrail.",
                policy_status="HALTED",
                candidates=[stop_candidate],
                metadata={"failure_code": "DUPLICATE_PAYMENT"},
            )

        # Determine available alternate payment methods (Edge Case 6)
        if available_payment_methods is not None:
            supported_alternatives = [m.upper() for m in available_payment_methods if m.upper() != current_method]
        else:
            supported_alternatives = ["UPI", "CARD", "NETBANKING", "WALLET"]
            if current_method in supported_alternatives:
                supported_alternatives.remove(current_method)

        # Build and evaluate candidates across all 6 actions
        candidates: List[RecoveryCandidate] = []
        for act in SUPPORTED_ACTIONS:
            # Determine probability: use injected probabilities if provided, else compute
            if action_probabilities and act in action_probabilities:
                prob = float(action_probabilities[act])
            else:
                prob = self.action_predictor.estimate_action_probability(txn, act)

            prob = float(max(0.0, min(1.0, prob)))
            ev = round(amount * prob, 2)

            # Evaluate policy permission for this candidate action
            eval_payload = dict(txn)
            eval_payload["action"] = act
            eval_payload["amount"] = amount
            eval_payload["risk_score"] = risk_score
            eval_payload["status"] = status
            eval_payload["failure_code"] = failure_code

            pol_decision = self.policy_engine.evaluate(
                event=eval_payload,
                customer_context=cust,
                previous_attempts=previous_attempts,
                customer_risk=risk_score,
            )

            permitted = pol_decision.allowed
            rejection_reason = pol_decision.reason if not permitted else None

            # Edge Case 6 check: Unsupported payment method for SWITCH_PAYMENT_METHOD
            parameters: Dict[str, Any] = {}
            if act == "SWITCH_PAYMENT_METHOD":
                if not supported_alternatives:
                    permitted = False
                    rejection_reason = "No alternative payment methods available for method switch."
                else:
                    parameters["suggested_method"] = supported_alternatives[0]

            if act == "SCHEDULE_RETRY":
                parameters["delay_seconds"] = 300

            # STOP is always structurally allowed as a terminal fallback
            if act == "STOP":
                permitted = True
                ev = 0.0

            candidates.append(
                RecoveryCandidate(
                    action=act,
                    probability=prob,
                    expected_recovery_value=ev,
                    permitted=permitted,
                    policy_outcome=pol_decision.outcome.value,
                    rule_id=pol_decision.rule_id,
                    rejection_reason=rejection_reason,
                    parameters=parameters,
                )
            )

        # Filter permitted candidates
        permitted_candidates = [c for c in candidates if c.permitted]

        # Edge Case 4: High-Risk payments (automated actions blocked, only ESCALATE or STOP)
        if risk_score > 0.85 or (classification and classification.category == FailureCategory.RISK):
            escalate_cands = [c for c in permitted_candidates if c.action == "ESCALATE"]
            if escalate_cands:
                chosen = escalate_cands[0]
                return RecoveryDecision(
                    transaction_id=txn_id,
                    selected_action="ESCALATE",
                    recovery_probability=chosen.probability,
                    expected_recovery_value=chosen.expected_recovery_value,
                    reasoning_summary=f"High risk score ({risk_score:.2f}) detected. Automated recovery blocked; escalated to risk operations.",
                    policy_status="ESCALATED",
                    candidates=candidates,
                    fallback_action="STOP",
                    metadata={"risk_score": risk_score},
                )
            else:
                return RecoveryDecision(
                    transaction_id=txn_id,
                    selected_action="STOP",
                    recovery_probability=0.0,
                    expected_recovery_value=0.0,
                    reasoning_summary=f"High risk score ({risk_score:.2f}) detected. All recovery actions halted.",
                    policy_status="HALTED",
                    candidates=candidates,
                    metadata={"risk_score": risk_score},
                )

        # Edge Case 7: Zero probability across all permitted candidates
        positive_ev_candidates = [c for c in permitted_candidates if c.expected_recovery_value > 0.0 and c.action != "STOP"]
        if not positive_ev_candidates:
            # Fall back to ESCALATE if policy suggests, otherwise STOP
            has_escalate = any(c.action == "ESCALATE" and c.permitted for c in permitted_candidates)
            selected = "ESCALATE" if has_escalate and risk_score > 0.40 else "STOP"
            return RecoveryDecision(
                transaction_id=txn_id,
                selected_action=selected,
                recovery_probability=0.0,
                expected_recovery_value=0.0,
                reasoning_summary="Zero expected recovery value across all candidate actions. Halted to prevent futile attempts.",
                policy_status="HALTED" if selected == "STOP" else "ESCALATED",
                candidates=candidates,
                fallback_action="STOP",
                metadata={"amount": amount},
            )

        # Edge Case 8: Sort permitted candidates by Expected Value descending, then Probability, then Action Priority
        def sort_key(c: RecoveryCandidate):
            # Deterministic priority index
            prio = ACTION_PRIORITY.index(c.action) if c.action in ACTION_PRIORITY else 99
            return (-c.expected_recovery_value, -c.probability, prio)

        sorted_permitted = sorted(positive_ev_candidates, key=sort_key)
        best = sorted_permitted[0]
        second_best = sorted_permitted[1].action if len(sorted_permitted) > 1 else "STOP"

        summary = (
            f"Selected '{best.action}' with expected recovery value of ₹{best.expected_recovery_value:,.2f} "
            f"(P={best.probability:.2%}) for transaction amount ₹{amount:,.2f}."
        )

        return RecoveryDecision(
            transaction_id=txn_id,
            selected_action=best.action,
            recovery_probability=best.probability,
            expected_recovery_value=best.expected_recovery_value,
            reasoning_summary=summary,
            policy_status="PERMITTED",
            candidates=candidates,
            fallback_action=second_best,
            metadata={
                "amount": amount,
                "failure_code": failure_code,
                "suggested_parameters": best.parameters,
            },
        )
