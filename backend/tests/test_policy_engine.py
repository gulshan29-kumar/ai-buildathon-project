from __future__ import annotations

import pytest

from backend.app.failure_classifier import FailureCategory
from backend.app.policy_engine import PolicyEngine


def test_policy_engine_duplicate_payment_stops():
    engine = PolicyEngine()
    decision = engine.evaluate({"failure_type": "DUPLICATE_PAYMENT", "recommended_action": "RETRY_PAYMENT"})
    assert decision.allowed is False
    assert decision.action == "STOP"
    assert decision.classification.category == FailureCategory.DUPLICATE
    assert "duplicate payment detected" in decision.reason.lower()


def test_policy_engine_expired_card_blocks_retry():
    engine = PolicyEngine()
    decision = engine.evaluate({"failure_type": "CARD_EXPIRED", "recommended_action": "RETRY_PAYMENT"})
    assert decision.allowed is False
    assert "expired card" in decision.reason.lower()


def test_policy_engine_high_risk_escalates():
    engine = PolicyEngine()
    decision = engine.evaluate(
        {"failure_type": "HIGH_RISK", "recommended_action": "RETRY_PAYMENT"},
        customer_risk=0.92,
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.classification.category == FailureCategory.RISK


def test_policy_engine_pending_payment_waits():
    engine = PolicyEngine()
    decision = engine.evaluate({"failure_type": "PAYMENT_PENDING", "recommended_action": "RETRY_PAYMENT"})
    assert decision.allowed is False
    assert decision.action == "WAIT_AND_POLL"
    assert decision.classification.category == FailureCategory.PENDING


def test_policy_engine_temporary_failure_allowed():
    engine = PolicyEngine()
    decision = engine.evaluate(
        {"failure_type": "GATEWAY_TIMEOUT", "recommended_action": "RETRY_PAYMENT"},
        previous_attempts=1,
        customer_risk=0.2,
    )
    assert decision.allowed is True
    assert decision.action == "RETRY_PAYMENT"
    assert decision.classification.category == FailureCategory.TEMPORARY
