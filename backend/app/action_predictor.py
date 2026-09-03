from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np

from backend.app.failure_classifier import FailureCategory, FailureClassifier
from backend.app.ml.inference import predict_recovery_probability


SUPPORTED_ACTIONS = [
    "RETRY_PAYMENT",
    "SWITCH_PAYMENT_METHOD",
    "SEND_RECOVERY_MESSAGE",
    "SCHEDULE_RETRY",
    "ESCALATE",
    "STOP",
]


class ActionRecoveryPredictor:
    """Estimates action-conditional recovery probabilities P(recovery | action) and expected value."""

    def __init__(self):
        # Action affinity profiles by failure category (action effectiveness multipliers)
        self.category_action_profiles = {
            FailureCategory.TEMPORARY: {
                "RETRY_PAYMENT": 0.86,
                "SCHEDULE_RETRY": 0.80,
                "SWITCH_PAYMENT_METHOD": 0.58,
                "SEND_RECOVERY_MESSAGE": 0.38,
                "ESCALATE": 0.22,
                "STOP": 0.00,
            },
            FailureCategory.PAYMENT_METHOD: {
                "RETRY_PAYMENT": 0.02,  # Expired or declined card retry is futile
                "SWITCH_PAYMENT_METHOD": 0.84,  # Switching card or moving to UPI has high success
                "SEND_RECOVERY_MESSAGE": 0.68,
                "SCHEDULE_RETRY": 0.05,
                "ESCALATE": 0.25,
                "STOP": 0.00,
            },
            FailureCategory.CUSTOMER: {  # e.g., INSUFFICIENT_FUNDS
                "RETRY_PAYMENT": 0.08,  # Immediate retry usually fails
                "SCHEDULE_RETRY": 0.58,  # Scheduled retry gives time to add funds
                "SWITCH_PAYMENT_METHOD": 0.74,  # Switch to an account with balance
                "SEND_RECOVERY_MESSAGE": 0.65,  # Reminder message to add funds
                "ESCALATE": 0.20,
                "STOP": 0.00,
            },
            FailureCategory.AUTHENTICATION: {  # OTP_FAILURE, AUTH_TIMEOUT
                "RETRY_PAYMENT": 0.78,  # Re-trigger OTP
                "SEND_RECOVERY_MESSAGE": 0.72,  # Send quick auth link
                "SWITCH_PAYMENT_METHOD": 0.64,
                "SCHEDULE_RETRY": 0.42,
                "ESCALATE": 0.20,
                "STOP": 0.00,
            },
            FailureCategory.BANK: {  # BANK_UNAVAILABLE
                "RETRY_PAYMENT": 0.15,  # Bank is down, immediate retry fails
                "SCHEDULE_RETRY": 0.82,  # Scheduled retry after downtime passes
                "SWITCH_PAYMENT_METHOD": 0.80,  # Switch to a different bank/instrument
                "SEND_RECOVERY_MESSAGE": 0.50,
                "ESCALATE": 0.25,
                "STOP": 0.00,
            },
            FailureCategory.ABANDONMENT: {  # CUSTOMER_ABANDONED
                "RETRY_PAYMENT": 0.02,  # No card details captured
                "SEND_RECOVERY_MESSAGE": 0.58,  # Meaningful recovery link conversion
                "SWITCH_PAYMENT_METHOD": 0.10,
                "SCHEDULE_RETRY": 0.05,
                "ESCALATE": 0.12,
                "STOP": 0.00,
            },
            FailureCategory.RISK: {  # HIGH_RISK, FRAUD
                "RETRY_PAYMENT": 0.00,  # Automatic recovery strictly blocked
                "SWITCH_PAYMENT_METHOD": 0.00,
                "SCHEDULE_RETRY": 0.00,
                "SEND_RECOVERY_MESSAGE": 0.00,
                "ESCALATE": 0.38,  # Manual fraud analyst review can unblock legitimate transactions
                "STOP": 0.00,
            },
            FailureCategory.DUPLICATE: {  # DUPLICATE_PAYMENT
                "RETRY_PAYMENT": 0.00,
                "SWITCH_PAYMENT_METHOD": 0.00,
                "SCHEDULE_RETRY": 0.00,
                "SEND_RECOVERY_MESSAGE": 0.00,
                "ESCALATE": 0.00,
                "STOP": 0.00,
            },
            FailureCategory.PENDING: {  # PAYMENT_PENDING
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
                "ESCALATE": 0.60,  # Contact merchant ops
                "STOP": 0.00,
            },
            FailureCategory.TECHNICAL: {
                "RETRY_PAYMENT": 0.65,
                "SCHEDULE_RETRY": 0.60,
                "SWITCH_PAYMENT_METHOD": 0.50,
                "SEND_RECOVERY_MESSAGE": 0.35,
                "ESCALATE": 0.25,
                "STOP": 0.00,
            },
        }

    def estimate_action_probability(
        self,
        transaction: Dict[str, Any],
        action: str,
    ) -> float:
        """Estimates P(recovery | action) for a specific action."""
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action: '{action}'. Must be one of {SUPPORTED_ACTIONS}")

        if action == "STOP":
            return 0.0

        # Extract failure context
        raw_code = transaction.get("failure_code") or transaction.get("failure_type") or "GATEWAY_TIMEOUT"
        classification = FailureClassifier.classify(raw_code)
        category = classification.category

        risk_score = float(transaction.get("risk_score", 0.05))
        amount = float(transaction.get("amount", 1000.0))
        attempt_number = int(transaction.get("attempt_number", 1))

        # Check safety guardrails: High risk blocks automatic recovery actions
        if (risk_score > 0.85 or category == FailureCategory.RISK) and action != "ESCALATE":
            return 0.0

        # Duplicate payments must not be recovered
        if category == FailureCategory.DUPLICATE or raw_code == "DUPLICATE_PAYMENT":
            return 0.0

        # Pending payments do not allow immediate recovery actions
        if category == FailureCategory.PENDING and action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
            return 0.0

        # Specific failure code constraints
        if raw_code == "CARD_EXPIRED" and action in {"RETRY_PAYMENT", "SCHEDULE_RETRY"}:
            return 0.01

        if raw_code == "INSUFFICIENT_FUNDS" and action == "RETRY_PAYMENT":
            return 0.06

        # Fetch base action probability from profile
        cat_profile = self.category_action_profiles.get(category, self.category_action_profiles[FailureCategory.TECHNICAL])
        base_prob = cat_profile.get(action, 0.20)

        # Modulate by transaction risk and customer success rate if available
        cust_success_rate = float(transaction.get("customer_success_rate", transaction.get("success_rate", 0.85)))
        success_modifier = 0.15 * (cust_success_rate - 0.70)
        risk_penalty = 0.20 * risk_score
        attempt_penalty = 0.08 * max(0, attempt_number - 1)

        prob = base_prob + success_modifier - risk_penalty - attempt_penalty

        # If action is ESCALATE on low risk, probability is lower than operational actions
        if action == "ESCALATE" and risk_score < 0.30:
            prob = min(prob, 0.25)

        return float(np.clip(round(prob, 4), 0.0, 0.98))

    def evaluate_action(
        self,
        transaction: Dict[str, Any],
        action: str,
    ) -> Dict[str, Any]:
        """Calculates recovery probability and expected recovery value for one action."""
        amount = float(transaction.get("amount", 0.0))
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
        """Calculates recovery probability and expected value across all supported actions."""
        return [self.evaluate_action(transaction, act) for act in SUPPORTED_ACTIONS]


# Singleton instance
_predictor_instance = ActionRecoveryPredictor()


def estimate_action_recovery(transaction: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Public helper to evaluate a single action."""
    return _predictor_instance.evaluate_action(transaction, action)


def evaluate_all_actions(transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Public helper to evaluate all 6 candidate actions."""
    return _predictor_instance.evaluate_all(transaction)
