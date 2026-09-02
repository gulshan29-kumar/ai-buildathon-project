from __future__ import annotations

import pytest

from backend.app.failure_classifier import (
    FailureCategory,
    FailureClassification,
    FailureClassifier,
    RecoverabilityLevel,
)


def test_all_eleven_categories_exist():
    expected_categories = {
        "TEMPORARY",
        "CUSTOMER",
        "PAYMENT_METHOD",
        "AUTHENTICATION",
        "BANK",
        "TECHNICAL",
        "RISK",
        "ABANDONMENT",
        "PENDING",
        "DUPLICATE",
        "MERCHANT",
    }
    actual_categories = {category.value for category in FailureCategory}
    assert actual_categories == expected_categories
    assert set(FailureClassifier.all_categories()) == expected_categories


def test_user_example_gateway_timeout():
    result = FailureClassifier.classify("GATEWAY_TIMEOUT")
    assert result.category == FailureCategory.TEMPORARY
    assert result.is_temporary is True
    assert result.temporary is True
    assert result.temporary_or_permanent == "TEMPORARY"
    assert result.recoverability_level == RecoverabilityLevel.HIGH
    assert result.recoverability == "HIGH"
    assert result.automatic_recovery is True
    assert result.recommended_action == "RETRY_PAYMENT"


def test_user_example_card_expired():
    result = FailureClassifier.classify("CARD_EXPIRED")
    assert result.category == FailureCategory.PAYMENT_METHOD
    assert result.is_temporary is False
    assert result.temporary is False
    assert result.temporary_or_permanent == "PERMANENT"
    assert result.recoverability_level == RecoverabilityLevel.LOW
    assert result.recoverability == "LOW"
    assert result.automatic_recovery is False
    assert result.recommended_action == "SWITCH_PAYMENT_METHOD"


def test_user_example_high_risk():
    result = FailureClassifier.classify("HIGH_RISK")
    assert result.category == FailureCategory.RISK
    assert result.is_temporary is False
    assert result.temporary_or_permanent == "PERMANENT"
    assert result.automatic_recovery is False
    assert result.requires_human_review is True
    assert result.recommended_action == "ESCALATE"


def test_user_example_payment_pending():
    result = FailureClassifier.classify("PAYMENT_PENDING")
    assert result.category == FailureCategory.PENDING
    assert result.is_temporary is True
    assert result.temporary_or_permanent == "TEMPORARY"
    assert result.automatic_recovery is False
    assert result.recommended_action == "WAIT_AND_POLL"
    assert "wait" in result.recommended_investigation.lower()


def test_user_example_duplicate_payment():
    result = FailureClassifier.classify("DUPLICATE_PAYMENT")
    assert result.category == FailureCategory.DUPLICATE
    assert result.is_temporary is False
    assert result.temporary_or_permanent == "PERMANENT"
    assert result.recoverability_level == RecoverabilityLevel.NONE
    assert result.automatic_recovery is False
    assert result.recommended_action == "STOP"


def test_bank_unavailable():
    result = FailureClassifier.classify("BANK_UNAVAILABLE")
    assert result.category == FailureCategory.BANK
    assert result.is_temporary is True
    assert result.temporary_or_permanent == "TEMPORARY"
    assert result.recoverability_level == RecoverabilityLevel.MEDIUM
    assert result.automatic_recovery is True
    assert result.recommended_action == "SCHEDULE_RETRY"


def test_insufficient_funds():
    result = FailureClassifier.classify("INSUFFICIENT_FUNDS")
    assert result.category == FailureCategory.CUSTOMER
    assert result.is_temporary is False
    assert result.temporary_or_permanent == "PERMANENT"
    assert result.recoverability_level == RecoverabilityLevel.LOW
    assert result.automatic_recovery is False
    assert result.recommended_action == "SEND_RECOVERY_MESSAGE"


def test_card_declined():
    result = FailureClassifier.classify("CARD_DECLINED")
    assert result.category == FailureCategory.PAYMENT_METHOD
    assert result.is_temporary is False
    assert result.recoverability_level == RecoverabilityLevel.MEDIUM
    assert result.automatic_recovery is False
    assert result.recommended_action == "SWITCH_PAYMENT_METHOD"


def test_authentication_failures():
    otp = FailureClassifier.classify("OTP_FAILURE")
    assert otp.category == FailureCategory.AUTHENTICATION
    assert otp.is_temporary is True
    assert otp.recoverability_level == RecoverabilityLevel.HIGH

    auth = FailureClassifier.classify("AUTH_TIMEOUT")
    assert auth.category == FailureCategory.AUTHENTICATION
    assert auth.is_temporary is True
    assert auth.recoverability_level == RecoverabilityLevel.HIGH


def test_abandonment_and_merchant_failures():
    abandoned = FailureClassifier.classify("CUSTOMER_ABANDONED")
    assert abandoned.category == FailureCategory.ABANDONMENT
    assert abandoned.is_temporary is True
    assert abandoned.recommended_action == "SEND_RECOVERY_MESSAGE"

    merchant = FailureClassifier.classify("ORDER_CREATION_FAILED")
    assert merchant.category == FailureCategory.MERCHANT
    assert merchant.is_temporary is False
    assert merchant.requires_human_review is True
    assert merchant.recommended_action == "ESCALATE"


def test_normalization_and_aliases():
    assert FailureClassifier.classify("gateway_timeout").failure_code == "GATEWAY_TIMEOUT"
    assert FailureClassifier.classify("  CARD_EXPIRED  ").failure_code == "CARD_EXPIRED"
    assert FailureClassifier.classify("INSUFFICIENT_BALANCE").failure_code == "INSUFFICIENT_FUNDS"
    assert FailureClassifier.classify("EXPIRED_CARD").failure_code == "CARD_EXPIRED"
    assert FailureClassifier.classify("CART_ABANDONED").failure_code == "CUSTOMER_ABANDONED"


def test_pattern_heuristics_for_vendor_variants():
    gw = FailureClassifier.classify("VENDOR_GATEWAY_TIMEOUT_504")
    assert gw.category == FailureCategory.TEMPORARY
    assert gw.is_temporary is True

    bank = FailureClassifier.classify("CORE_BANK_DOWN_ERROR")
    assert bank.category == FailureCategory.BANK
    assert bank.is_temporary is True

    risk = FailureClassifier.classify("CUSTOM_RISK_FRAUD_SUSPECTED")
    assert risk.category == FailureCategory.RISK
    assert risk.requires_human_review is True


def test_unknown_fallback():
    result = FailureClassifier.classify("TOTALLY_UNKNOWN_ERROR_CODE_XYZ")
    assert result.category == FailureCategory.TECHNICAL
    assert result.requires_human_review is True
    assert result.automatic_recovery is False
    assert result.recommended_action == "ESCALATE"


def test_classify_many_and_serialization():
    codes = ["GATEWAY_TIMEOUT", "CARD_EXPIRED", "HIGH_RISK"]
    results = FailureClassifier.classify_many(codes)
    assert len(results) == 3
    assert results[0].failure_code == "GATEWAY_TIMEOUT"
    assert results[1].failure_code == "CARD_EXPIRED"
    assert results[2].failure_code == "HIGH_RISK"

    d = results[0].to_dict()
    assert d["category"] == "TEMPORARY"
    assert d["temporary"] is True
    assert d["recoverability"] == "HIGH"
