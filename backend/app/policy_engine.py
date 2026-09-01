from typing import Dict, List, Optional


class PolicyDecision:
    def __init__(self, allowed: bool, reason: str, action: Optional[str] = None):
        self.allowed = allowed
        self.reason = reason
        self.action = action


class PolicyEngine:
    def __init__(self):
        self.retry_limits = {"RETRY_PAYMENT": 2, "SCHEDULE_RETRY": 3}
        self.blocked_failures = {"DUPLICATE_PAYMENT", "ORDER_CREATION_FAILED"}

    def evaluate(self, event: Dict, previous_attempts: int = 0, customer_risk: float = 0.0) -> PolicyDecision:
        failure_type = event.get("failure_type")
        action = event.get("recommended_action")

        if failure_type in self.blocked_failures:
            return PolicyDecision(False, "Blocked by safety policy for duplicate or merchant-order failure.", action)

        if action == "RETRY_PAYMENT" and previous_attempts >= self.retry_limits.get("RETRY_PAYMENT", 2):
            return PolicyDecision(False, "Retry limit exceeded for payment retry action.", action)

        if customer_risk > 0.85 and action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
            return PolicyDecision(False, "Customer risk threshold exceeds allowed policy band.", action)

        return PolicyDecision(True, "Action is permitted under deterministic policy checks.", action)


if __name__ == "__main__":
    engine = PolicyEngine()
    decision = engine.evaluate({"failure_type": "BANK_UNAVAILABLE", "recommended_action": "RETRY_PAYMENT"}, previous_attempts=1, customer_risk=0.4)
    print(decision.allowed, decision.reason)
