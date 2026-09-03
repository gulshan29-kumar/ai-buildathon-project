from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np

from backend.app.failure_classifier import FailureCategory, FailureClassifier

SUPPORTED_ACTIONS = [
    "RETRY_PAYMENT",
    "SWITCH_PAYMENT_METHOD",
    "SEND_RECOVERY_MESSAGE",
    "SCHEDULE_RETRY",
    "ESCALATE",
    "STOP",
]

# Synthetic historical benchmark outcomes derived from simulation sandbox runs (10,000+ simulated events)
SYNTHETIC_SIMULATOR_OUTCOMES: Dict[str, Dict[str, float]] = {
    "GATEWAY_TIMEOUT": {
        "RETRY_PAYMENT": 0.82,  # 82% success rate on retry in simulator
        "SCHEDULE_RETRY": 0.78,
        "SWITCH_PAYMENT_METHOD": 0.55,
        "SEND_RECOVERY_MESSAGE": 0.35,
        "ESCALATE": 0.18,
        "STOP": 0.00,
    },
    "CARD_EXPIRED": {
        "RETRY_PAYMENT": 0.00,  # 0% success retrying expired card in simulator
        "SWITCH_PAYMENT_METHOD": 0.85,  # 85% recovery switching to UPI/alternate instrument
        "SEND_RECOVERY_MESSAGE": 0.65,  # 65% recovery sending link to update card
        "SCHEDULE_RETRY": 0.02,  # Expired card won't resolve over time
        "ESCALATE": 0.15,
        "STOP": 0.00,
    },
    "INSUFFICIENT_FUNDS": {
        "RETRY_PAYMENT": 0.08,  # 8% immediate retry success in simulator
        "SCHEDULE_RETRY": 0.65,  # 65% delayed retry success (>= 300s) giving time to add funds
        "SWITCH_PAYMENT_METHOD": 0.75,  # Switch to alternate payment source
        "SEND_RECOVERY_MESSAGE": 0.60,  # Reminder prompt to top up account
        "ESCALATE": 0.15,
        "STOP": 0.00,
    },
    "CUSTOMER_ABANDONED": {
        "RETRY_PAYMENT": 0.00,  # Cannot retry unauthenticated / abandoned checkout
        "SEND_RECOVERY_MESSAGE": 0.70,  # 70% customer return & conversion from recovery message
        "SWITCH_PAYMENT_METHOD": 0.12,
        "SCHEDULE_RETRY": 0.05,
        "ESCALATE": 0.10,
        "STOP": 0.00,
    },
    "HIGH_RISK": {
        "RETRY_PAYMENT": 0.00,  # Automatic recovery strictly blocked by policy
        "SWITCH_PAYMENT_METHOD": 0.00,
        "SEND_RECOVERY_MESSAGE": 0.00,
        "SCHEDULE_RETRY": 0.00,
        "ESCALATE": 0.35,  # Manual fraud operations analyst clearance
        "STOP": 0.00,
    },
    "BANK_UNAVAILABLE": {
        "RETRY_PAYMENT": 0.12,  # Bank is temporarily down; immediate retry fails
        "SCHEDULE_RETRY": 0.82,  # High recovery after bank downtime window
        "SWITCH_PAYMENT_METHOD": 0.82,  # Switch to UPI or alternate acquiring bank
        "SEND_RECOVERY_MESSAGE": 0.45,
        "ESCALATE": 0.20,
        "STOP": 0.00,
    },
    "OTP_FAILURE": {
        "RETRY_PAYMENT": 0.76,  # Resend OTP
        "SEND_RECOVERY_MESSAGE": 0.70,  # Send 1-click checkout recovery link
        "SWITCH_PAYMENT_METHOD": 0.62,
        "SCHEDULE_RETRY": 0.38,
        "ESCALATE": 0.15,
        "STOP": 0.00,
    },
    "AUTH_TIMEOUT": {
        "RETRY_PAYMENT": 0.72,
        "SEND_RECOVERY_MESSAGE": 0.68,
        "SWITCH_PAYMENT_METHOD": 0.58,
        "SCHEDULE_RETRY": 0.45,
        "ESCALATE": 0.15,
        "STOP": 0.00,
    },
    "CARD_DECLINED": {
        "RETRY_PAYMENT": 0.04,  # General decline rarely succeeds immediately
        "SWITCH_PAYMENT_METHOD": 0.82,  # Switch to UPI or another card
        "SEND_RECOVERY_MESSAGE": 0.64,
        "SCHEDULE_RETRY": 0.10,
        "ESCALATE": 0.20,
        "STOP": 0.00,
    },
    "DUPLICATE_PAYMENT": {
        "RETRY_PAYMENT": 0.00,
        "SWITCH_PAYMENT_METHOD": 0.00,
        "SEND_RECOVERY_MESSAGE": 0.00,
        "SCHEDULE_RETRY": 0.00,
        "ESCALATE": 0.00,
        "STOP": 0.00,
    },
    "PAYMENT_PENDING": {
        "RETRY_PAYMENT": 0.00,
        "SWITCH_PAYMENT_METHOD": 0.00,
        "SEND_RECOVERY_MESSAGE": 0.00,
        "SCHEDULE_RETRY": 0.00,
        "ESCALATE": 0.10,
        "STOP": 0.00,
    },
}


class ActionRecoveryPredictor:
    """Estimates action-conditional recovery probabilities P(recovery | action) and expected recovery value."""

    def __init__(
        self,
        synthetic_benchmarks: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.synthetic_simulator_outcomes = (
            synthetic_benchmarks if synthetic_benchmarks is not None else SYNTHETIC_SIMULATOR_OUTCOMES
        )

        # Action affinity profiles by failure category (fallback for unmapped failure codes)
        self.category_action_profiles: Dict[FailureCategory, Dict[str, float]] = {
            FailureCategory.TEMPORARY: {
                "RETRY_PAYMENT": 0.82,
                "SCHEDULE_RETRY": 0.78,
                "SWITCH_PAYMENT_METHOD": 0.55,
                "SEND_RECOVERY_MESSAGE": 0.35,
                "ESCALATE": 0.18,
                "STOP": 0.00,
            },
            FailureCategory.PAYMENT_METHOD: {
                "RETRY_PAYMENT": 0.02,
                "SWITCH_PAYMENT_METHOD": 0.84,
                "SEND_RECOVERY_MESSAGE": 0.65,
                "SCHEDULE_RETRY": 0.05,
                "ESCALATE": 0.18,
                "STOP": 0.00,
            },
            FailureCategory.CUSTOMER: {
                "RETRY_PAYMENT": 0.08,
                "SCHEDULE_RETRY": 0.65,
                "SWITCH_PAYMENT_METHOD": 0.74,
                "SEND_RECOVERY_MESSAGE": 0.60,
                "ESCALATE": 0.15,
                "STOP": 0.00,
            },
            FailureCategory.AUTHENTICATION: {
                "RETRY_PAYMENT": 0.75,
                "SEND_RECOVERY_MESSAGE": 0.70,
                "SWITCH_PAYMENT_METHOD": 0.62,
                "SCHEDULE_RETRY": 0.40,
                "ESCALATE": 0.15,
                "STOP": 0.00,
            },
            FailureCategory.BANK: {
                "RETRY_PAYMENT": 0.12,
                "SCHEDULE_RETRY": 0.82,
                "SWITCH_PAYMENT_METHOD": 0.82,
                "SEND_RECOVERY_MESSAGE": 0.45,
                "ESCALATE": 0.20,
                "STOP": 0.00,
            },
            FailureCategory.ABANDONMENT: {
                "RETRY_PAYMENT": 0.00,
                "SEND_RECOVERY_MESSAGE": 0.70,
                "SWITCH_PAYMENT_METHOD": 0.12,
                "SCHEDULE_RETRY": 0.05,
                "ESCALATE": 0.10,
                "STOP": 0.00,
            },
            FailureCategory.RISK: {
                "RETRY_PAYMENT": 0.00,
                "SWITCH_PAYMENT_METHOD": 0.00,
                "SEND_RECOVERY_MESSAGE": 0.00,
                "SCHEDULE_RETRY": 0.00,
                "ESCALATE": 0.35,
                "STOP": 0.00,
            },
            FailureCategory.DUPLICATE: {
                "RETRY_PAYMENT": 0.00,
                "SWITCH_PAYMENT_METHOD": 0.00,
                "SEND_RECOVERY_MESSAGE": 0.00,
                "SCHEDULE_RETRY": 0.00,
                "ESCALATE": 0.00,
                "STOP": 0.00,
            },
            FailureCategory.PENDING: {
                "RETRY_PAYMENT": 0.00,
                "SWITCH_PAYMENT_METHOD": 0.00,
                "SCHEDULE_RETRY": 0.00,
                "SEND_RECOVERY_MESSAGE": 0.00,
                "ESCALATE": 0.10,
                "STOP": 0.00,
            },
            FailureCategory.MERCHANT: {
                "RETRY_PAYMENT": 0.05,
                "SWITCH_PAYMENT_METHOD": 0.05,
                "SCHEDULE_RETRY": 0.05,
                "SEND_RECOVERY_MESSAGE": 0.10,
                "ESCALATE": 0.60,
                "STOP": 0.00,
            },
            FailureCategory.TECHNICAL: {
                "RETRY_PAYMENT": 0.65,
                "SCHEDULE_RETRY": 0.60,
                "SWITCH_PAYMENT_METHOD": 0.50,
                "SEND_RECOVERY_MESSAGE": 0.35,
                "ESCALATE": 0.22,
                "STOP": 0.00,
            },
        }

    def estimate_action_probability(
        self,
        transaction: Dict[str, Any],
        action: str,
    ) -> float:
        """Estimates P(recovery | action) for a transaction given a candidate recovery action."""
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action: '{action}'. Must be one of {SUPPORTED_ACTIONS}")

        # STOP action never recovers funds
        if action == "STOP":
            return 0.0

        # Extract failure context
        raw_code = str(transaction.get("failure_code") or transaction.get("failure_type") or "GATEWAY_TIMEOUT").upper()
        classification = FailureClassifier.classify(raw_code)
        category = classification.category

        try:
            risk_score = max(0.0, min(1.0, float(transaction.get("risk_score", 0.05))))
        except (ValueError, TypeError):
            risk_score = 0.05

        try:
            attempt_number = max(1, int(transaction.get("attempt_number", 1)))
        except (ValueError, TypeError):
            attempt_number = 1

        # Hard Guardrail 1: High risk (risk_score > 0.85 or category == RISK) strictly blocks automatic recovery
        if (risk_score > 0.85 or category == FailureCategory.RISK) and action != "ESCALATE":
            return 0.0

        # Hard Guardrail 2: Duplicate payments must never be re-attempted
        if category == FailureCategory.DUPLICATE or raw_code == "DUPLICATE_PAYMENT":
            return 0.0

        # Hard Guardrail 3: Pending payments do not allow immediate recovery re-attempts
        if category == FailureCategory.PENDING and action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
            return 0.0

        # Specific failure code guardrails directly aligned with simulator causal dynamics
        if raw_code == "CARD_EXPIRED":
            if action in {"RETRY_PAYMENT", "SCHEDULE_RETRY"}:
                return 0.0  # Retrying the same expired card is 0% effective
            if action == "SWITCH_PAYMENT_METHOD":
                return 0.85

        if raw_code == "INSUFFICIENT_FUNDS" and action == "RETRY_PAYMENT":
            return 0.08  # Immediate retry on insufficient funds fails 92% of the time

        if raw_code == "CUSTOMER_ABANDONED" and action in {"RETRY_PAYMENT", "SCHEDULE_RETRY"}:
            return 0.0  # No payment credentials captured; direct retry cannot be dispatched

        # Fetch base action probability from synthetic simulator benchmarks or category profile
        if raw_code in self.synthetic_simulator_outcomes:
            base_prob = self.synthetic_simulator_outcomes[raw_code].get(action, 0.20)
        else:
            cat_profile = self.category_action_profiles.get(
                category, self.category_action_profiles[FailureCategory.TECHNICAL]
            )
            base_prob = cat_profile.get(action, 0.20)

        # Modulate by transaction risk and customer historical success rate if provided
        try:
            cust_success_rate = float(
                transaction.get("customer_success_rate", transaction.get("success_rate", 0.85))
            )
        except (ValueError, TypeError):
            cust_success_rate = 0.85

        success_modifier = 0.12 * (cust_success_rate - 0.70)
        risk_penalty = 0.18 * risk_score
        attempt_penalty = 0.06 * max(0, attempt_number - 1)

        prob = base_prob + success_modifier - risk_penalty - attempt_penalty

        # If action is ESCALATE on low risk, probability of recovery is lower than direct operational actions
        if action == "ESCALATE" and risk_score < 0.30:
            prob = min(prob, 0.25)

        return float(np.clip(round(prob, 4), 0.0, 0.98))

    def evaluate_action(
        self,
        transaction: Dict[str, Any],
        action: str,
    ) -> Dict[str, Any]:
        """Calculates recovery probability P(recovery | action) and expected recovery value (amount * probability)."""
        try:
            amount = max(0.0, float(transaction.get("amount", 0.0)))
        except (ValueError, TypeError):
            amount = 0.0

        prob = self.estimate_action_probability(transaction, action)
        expected_value = round(amount * prob, 2)

        return {
            "action": action,
            "probability": prob,
            "expected_recovery_value": expected_value,
        }

    def evaluate_all(
        self,
        transaction: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Calculates recovery probability and expected recovery value across all 6 supported actions."""
        return [self.evaluate_action(transaction, act) for act in SUPPORTED_ACTIONS]


# Singleton instance
_predictor_instance = ActionRecoveryPredictor()


def predict_action_recovery(transaction: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Estimates recovery probability and expected value for a single candidate action."""
    return _predictor_instance.evaluate_action(transaction, action)


def predict_all_action_recoveries(transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Estimates recovery probability and expected value across all 6 candidate actions."""
    return _predictor_instance.evaluate_all(transaction)


# Backward-compatible alias helpers
estimate_action_recovery = predict_action_recovery
evaluate_all_actions = predict_all_action_recoveries
