from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class FailureCategory(str, Enum):
    TEMPORARY = "TEMPORARY"
    CUSTOMER = "CUSTOMER"
    PAYMENT_METHOD = "PAYMENT_METHOD"
    AUTHENTICATION = "AUTHENTICATION"
    BANK = "BANK"
    TECHNICAL = "TECHNICAL"
    RISK = "RISK"
    ABANDONMENT = "ABANDONMENT"
    PENDING = "PENDING"
    DUPLICATE = "DUPLICATE"
    MERCHANT = "MERCHANT"


class RecoverabilityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


@dataclass(frozen=True)
class FailureClassification:
    failure_code: str
    category: FailureCategory
    is_temporary: bool
    temporary_or_permanent: str  # "TEMPORARY" | "PERMANENT"
    recoverability_level: RecoverabilityLevel
    automatic_recovery: bool
    recommended_action: str
    recommended_investigation: str
    requires_human_review: bool

    @property
    def temporary(self) -> bool:
        """Alias for is_temporary matching common property conventions."""
        return self.is_temporary

    @property
    def recoverability(self) -> str:
        """Alias for recoverability_level value string."""
        return self.recoverability_level.value

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["recoverability_level"] = self.recoverability_level.value
        data["temporary"] = self.is_temporary
        data["recoverability"] = self.recoverability_level.value
        return data


class FailureClassifier:
    """Deterministic failure classification engine for payment failures.

    Applies deterministic business rules to classify failure codes into standard
    categories, assess temporality, gauge recoverability levels, and determine safe
    action recommendations without invoking LLMs for known error patterns.
    """

    # Exact deterministic taxonomy mappings for known payment failure codes
    _TAXONOMY: Dict[str, FailureClassification] = {
        "GATEWAY_TIMEOUT": FailureClassification(
            failure_code="GATEWAY_TIMEOUT",
            category=FailureCategory.TEMPORARY,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.HIGH,
            automatic_recovery=True,
            recommended_action="RETRY_PAYMENT",
            recommended_investigation="Transient gateway congestion or network timeout. Retry with exponential backoff.",
            requires_human_review=False,
        ),
        "BANK_UNAVAILABLE": FailureClassification(
            failure_code="BANK_UNAVAILABLE",
            category=FailureCategory.BANK,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.MEDIUM,
            automatic_recovery=True,
            recommended_action="SCHEDULE_RETRY",
            recommended_investigation="Core banking system unreachable or undergoing downtime. Schedule delayed retry or switch payment method.",
            requires_human_review=False,
        ),
        "INSUFFICIENT_FUNDS": FailureClassification(
            failure_code="INSUFFICIENT_FUNDS",
            category=FailureCategory.CUSTOMER,
            is_temporary=False,
            temporary_or_permanent="PERMANENT",
            recoverability_level=RecoverabilityLevel.LOW,
            automatic_recovery=False,
            recommended_action="SEND_RECOVERY_MESSAGE",
            recommended_investigation="Customer account balance insufficient. Do not retry immediately; prompt customer via payment link or notification.",
            requires_human_review=False,
        ),
        "CARD_DECLINED": FailureClassification(
            failure_code="CARD_DECLINED",
            category=FailureCategory.PAYMENT_METHOD,
            is_temporary=False,
            temporary_or_permanent="PERMANENT",
            recoverability_level=RecoverabilityLevel.MEDIUM,
            automatic_recovery=False,
            recommended_action="SWITCH_PAYMENT_METHOD",
            recommended_investigation="Card issuer declined transaction. Prompt customer to use alternate card or payment method (e.g. UPI).",
            requires_human_review=False,
        ),
        "CARD_EXPIRED": FailureClassification(
            failure_code="CARD_EXPIRED",
            category=FailureCategory.PAYMENT_METHOD,
            is_temporary=False,
            temporary_or_permanent="PERMANENT",
            recoverability_level=RecoverabilityLevel.LOW,
            automatic_recovery=False,
            recommended_action="SWITCH_PAYMENT_METHOD",
            recommended_investigation="Card expiration date elapsed. Retrying the same card will never succeed; require card details update or method switch.",
            requires_human_review=False,
        ),
        "OTP_FAILURE": FailureClassification(
            failure_code="OTP_FAILURE",
            category=FailureCategory.AUTHENTICATION,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.HIGH,
            automatic_recovery=False,
            recommended_action="SEND_RECOVERY_MESSAGE",
            recommended_investigation="Customer 2FA OTP incorrect or expired. Send retry prompt or checkout recovery link to customer.",
            requires_human_review=False,
        ),
        "AUTH_TIMEOUT": FailureClassification(
            failure_code="AUTH_TIMEOUT",
            category=FailureCategory.AUTHENTICATION,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.HIGH,
            automatic_recovery=False,
            recommended_action="SEND_RECOVERY_MESSAGE",
            recommended_investigation="Customer authentication session window closed. Send checkout completion reminder.",
            requires_human_review=False,
        ),
        "HIGH_RISK": FailureClassification(
            failure_code="HIGH_RISK",
            category=FailureCategory.RISK,
            is_temporary=False,
            temporary_or_permanent="PERMANENT",
            recoverability_level=RecoverabilityLevel.NONE,
            automatic_recovery=False,
            recommended_action="ESCALATE",
            recommended_investigation="Fraud or velocity risk score threshold exceeded. Do not retry automatically; escalate to risk/compliance review.",
            requires_human_review=True,
        ),
        "CUSTOMER_ABANDONED": FailureClassification(
            failure_code="CUSTOMER_ABANDONED",
            category=FailureCategory.ABANDONMENT,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.MEDIUM,
            automatic_recovery=False,
            recommended_action="SEND_RECOVERY_MESSAGE",
            recommended_investigation="Customer dropped off during checkout flow. Send personalized cart recovery notification.",
            requires_human_review=False,
        ),
        "PAYMENT_PENDING": FailureClassification(
            failure_code="PAYMENT_PENDING",
            category=FailureCategory.PENDING,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.HIGH,
            automatic_recovery=False,
            recommended_action="WAIT_AND_POLL",
            recommended_investigation="Transaction settlement in progress. Wait and poll webhook/gateway status instead of triggering duplicate retry.",
            requires_human_review=False,
        ),
        "DUPLICATE_PAYMENT": FailureClassification(
            failure_code="DUPLICATE_PAYMENT",
            category=FailureCategory.DUPLICATE,
            is_temporary=False,
            temporary_or_permanent="PERMANENT",
            recoverability_level=RecoverabilityLevel.NONE,
            automatic_recovery=False,
            recommended_action="STOP",
            recommended_investigation="Duplicate payment attempt detected for same customer, merchant, and order. Halt execution immediately to prevent double billing.",
            requires_human_review=False,
        ),
        "ORDER_CREATION_FAILED": FailureClassification(
            failure_code="ORDER_CREATION_FAILED",
            category=FailureCategory.MERCHANT,
            is_temporary=False,
            temporary_or_permanent="PERMANENT",
            recoverability_level=RecoverabilityLevel.LOW,
            automatic_recovery=False,
            recommended_action="ESCALATE",
            recommended_investigation="Merchant backend failed to create order. Inspect merchant API integration, signature, and payload parameters.",
            requires_human_review=True,
        ),
    }

    # Code aliases for compatibility with vendor error strings
    _ALIASES: Dict[str, str] = {
        "TIMEOUT": "GATEWAY_TIMEOUT",
        "GATEWAY_ERROR": "GATEWAY_TIMEOUT",
        "BANK_DOWN": "BANK_UNAVAILABLE",
        "CORE_BANKING_ERROR": "BANK_UNAVAILABLE",
        "INSUFFICIENT_BALANCE": "INSUFFICIENT_FUNDS",
        "LOW_BALANCE": "INSUFFICIENT_FUNDS",
        "DECLINED": "CARD_DECLINED",
        "DO_NOT_HONOR": "CARD_DECLINED",
        "EXPIRED_CARD": "CARD_EXPIRED",
        "OTP_EXPIRED": "OTP_FAILURE",
        "INVALID_OTP": "OTP_FAILURE",
        "AUTHENTICATION_FAILED": "AUTH_TIMEOUT",
        "SESSION_EXPIRED": "AUTH_TIMEOUT",
        "FRAUD_SUSPECTED": "HIGH_RISK",
        "ABANDONED": "CUSTOMER_ABANDONED",
        "CART_ABANDONED": "CUSTOMER_ABANDONED",
        "PENDING": "PAYMENT_PENDING",
        "PROCESSING": "PAYMENT_PENDING",
        "DUPLICATE_TRANSACTION": "DUPLICATE_PAYMENT",
        "ORDER_ERROR": "ORDER_CREATION_FAILED",
    }

    @classmethod
    def normalize_code(cls, code: Optional[str]) -> str:
        """Sanitizes and normalizes failure code input."""
        if not code:
            return "UNKNOWN"
        cleaned = code.strip().upper().replace(" ", "_").replace("-", "_")
        return cls._ALIASES.get(cleaned, cleaned)

    @classmethod
    def classify(
        cls,
        failure_code: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FailureClassification:
        """Deterministically classifies a failure code into taxonomy properties.

        Guarantees deterministic O(1) resolution without invoking an LLM.
        """
        normalized = cls.normalize_code(failure_code)

        if normalized in cls._TAXONOMY:
            return cls._TAXONOMY[normalized]

        # Pattern-based heuristics for unknown vendor codes
        if "TIMEOUT" in normalized or "GATEWAY" in normalized:
            return FailureClassification(
                failure_code=normalized,
                category=FailureCategory.TEMPORARY,
                is_temporary=True,
                temporary_or_permanent="TEMPORARY",
                recoverability_level=RecoverabilityLevel.HIGH,
                automatic_recovery=True,
                recommended_action="RETRY_PAYMENT",
                recommended_investigation=f"Transient network or gateway issue detected for '{normalized}'. Exponential retry recommended.",
                requires_human_review=False,
            )

        if "BANK" in normalized:
            return FailureClassification(
                failure_code=normalized,
                category=FailureCategory.BANK,
                is_temporary=True,
                temporary_or_permanent="TEMPORARY",
                recoverability_level=RecoverabilityLevel.MEDIUM,
                automatic_recovery=True,
                recommended_action="SCHEDULE_RETRY",
                recommended_investigation=f"Bank-side disruption indicated by '{normalized}'. Schedule delayed retry or switch rails.",
                requires_human_review=False,
            )

        if "CARD" in normalized:
            return FailureClassification(
                failure_code=normalized,
                category=FailureCategory.PAYMENT_METHOD,
                is_temporary=False,
                temporary_or_permanent="PERMANENT",
                recoverability_level=RecoverabilityLevel.LOW,
                automatic_recovery=False,
                recommended_action="SWITCH_PAYMENT_METHOD",
                recommended_investigation=f"Card-specific issue indicated by '{normalized}'. Prompt for alternative payment method.",
                requires_human_review=False,
            )

        if "RISK" in normalized or "FRAUD" in normalized:
            return FailureClassification(
                failure_code=normalized,
                category=FailureCategory.RISK,
                is_temporary=False,
                temporary_or_permanent="PERMANENT",
                recoverability_level=RecoverabilityLevel.NONE,
                automatic_recovery=False,
                recommended_action="ESCALATE",
                recommended_investigation=f"Risk/fraud trigger identified in '{normalized}'. Escalate for compliance review.",
                requires_human_review=True,
            )

        # Fallback for completely unrecognized failure codes
        return FailureClassification(
            failure_code=normalized,
            category=FailureCategory.TECHNICAL,
            is_temporary=True,
            temporary_or_permanent="TEMPORARY",
            recoverability_level=RecoverabilityLevel.LOW,
            automatic_recovery=False,
            recommended_action="ESCALATE",
            recommended_investigation=f"Unrecognized failure code '{normalized}'. Inspect raw gateway response logs and escalate.",
            requires_human_review=True,
        )

    @classmethod
    def classify_many(cls, failure_codes: List[str]) -> List[FailureClassification]:
        """Classifies a batch of failure codes."""
        return [cls.classify(code) for code in failure_codes]

    @classmethod
    def all_known_codes(cls) -> List[str]:
        """Returns all recognized canonical failure codes."""
        return list(cls._TAXONOMY.keys())

    @classmethod
    def all_categories(cls) -> List[str]:
        """Returns all 11 supported failure categories."""
        return [category.value for category in FailureCategory]
