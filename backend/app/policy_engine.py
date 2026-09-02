from typing import Any, Dict, List, Optional

from backend.app.failure_classifier import (
    FailureCategory,
    FailureClassification,
    FailureClassifier,
)


class PolicyDecision:
    def __init__(
        self,
        allowed: bool,
        reason: str,
        action: Optional[str] = None,
        classification: Optional[FailureClassification] = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.action = action
        self.classification = classification


class PolicyEngine:
    def __init__(self):
        self.retry_limits = {"RETRY_PAYMENT": 2, "SCHEDULE_RETRY": 3}
        self.blocked_failures = {"DUPLICATE_PAYMENT", "ORDER_CREATION_FAILED"}

    def evaluate(
        self,
        event: Dict[str, Any],
        previous_attempts: int = 0,
        customer_risk: float = 0.0,
    ) -> PolicyDecision:
        failure_type = event.get("failure_type") or event.get("failure_code")
        action = event.get("recommended_action") or event.get("action")
        classification = FailureClassifier.classify(failure_type)

        # Policy Rule 1: Duplicate payment detected must always STOP
        if classification.category == FailureCategory.DUPLICATE or failure_type == "DUPLICATE_PAYMENT":
            return PolicyDecision(
                allowed=False,
                reason="Blocked by safety policy: Duplicate payment detected. Execution halted.",
                action="STOP",
                classification=classification,
            )

        # Policy Rule 2: Expired card can never be retried with the same card
        if failure_type == "CARD_EXPIRED" and action == "RETRY_PAYMENT":
            return PolicyDecision(
                allowed=False,
                reason="Blocked by safety policy: Cannot retry on an expired card. Switch payment method required.",
                action=action,
                classification=classification,
            )

        # Policy Rule 3: High risk / fraud blocks automatic payment actions
        if customer_risk > 0.85 or classification.category == FailureCategory.RISK:
            if action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
                return PolicyDecision(
                    allowed=False,
                    reason="Blocked by safety policy: Risk threshold exceeded. Escalate to manual review.",
                    action="ESCALATE",
                    classification=classification,
                )

        # Policy Rule 4: Payment pending requires waiting, not retrying
        if classification.category == FailureCategory.PENDING and action == "RETRY_PAYMENT":
            return PolicyDecision(
                allowed=False,
                reason="Blocked by safety policy: Payment is pending settlement. Wait and poll status instead of retrying.",
                action="WAIT_AND_POLL",
                classification=classification,
            )

        # Policy Rule 5: Non-recoverable failures cannot use automatic retry
        if not classification.automatic_recovery and action == "RETRY_PAYMENT":
            return PolicyDecision(
                allowed=False,
                reason=f"Blocked by safety policy: Automatic retry not permitted for '{classification.failure_code}'. {classification.recommended_investigation}",
                action=action,
                classification=classification,
            )

        # Policy Rule 6: Retry count limits
        if action == "RETRY_PAYMENT" and previous_attempts >= self.retry_limits.get("RETRY_PAYMENT", 2):
            return PolicyDecision(
                allowed=False,
                reason="Retry limit exceeded for payment retry action.",
                action=action,
                classification=classification,
            )

        return PolicyDecision(
            allowed=True,
            reason="Action is permitted under deterministic policy checks.",
            action=action,
            classification=classification,
        )


if __name__ == "__main__":
    engine = PolicyEngine()
    decision = engine.evaluate(
        {"failure_type": "BANK_UNAVAILABLE", "recommended_action": "SCHEDULE_RETRY"},
        previous_attempts=1,
        customer_risk=0.4,
    )
    print(decision.allowed, decision.reason, decision.classification.category.value)

