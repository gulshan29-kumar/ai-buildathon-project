from __future__ import annotations

import pytest

from backend.app.ml.inference import (
    RecoveryPredictor,
    predict_recovery_probability,
)


def test_predict_recovery_probability_schema():
    txn = {
        "amount": 2500.0,
        "payment_method": "UPI",
        "gateway": "GATEWAY_A",
        "failure_code": "GATEWAY_TIMEOUT",
        "failure_category": "TEMPORARY",
        "attempt_number": 1,
        "customer_transaction_count": 25,
        "customer_success_rate": 0.92,
        "customer_average_transaction": 2200.0,
        "preferred_payment_method": "UPI",
        "risk_score": 0.05,
        "checkout_duration": 45.0,
        "device_type": "MOBILE",
        "hour": 14,
        "historical_failure_count": 1,
    }

    result = predict_recovery_probability(txn)
    assert "probability" in result
    assert "model_version" in result
    assert "important_features" in result
    assert "predicted_label" in result

    assert isinstance(result["probability"], float)
    assert 0.0 <= result["probability"] <= 1.0
    assert result["predicted_label"] in {0, 1}
    assert isinstance(result["model_version"], str)
    assert len(result["important_features"]) > 0

    for feat in result["important_features"]:
        assert "feature" in feat
        assert "importance" in feat
        assert isinstance(feat["importance"], (int, float))


def test_sparse_input_defaults():
    # Only minimal keys provided
    minimal_txn = {
        "amount": 500.0,
        "payment_method": "CARD",
        "failure_code": "CARD_DECLINED",
    }
    result = predict_recovery_probability(minimal_txn)
    assert 0.0 <= result["probability"] <= 1.0
    assert len(result["important_features"]) > 0


def test_high_risk_low_probability():
    high_risk_txn = {
        "amount": 50000.0,
        "payment_method": "CARD",
        "failure_code": "HIGH_RISK",
        "failure_category": "RISK",
        "risk_score": 0.95,
        "customer_success_rate": 0.20,
    }
    result = predict_recovery_probability(high_risk_txn)
    assert result["probability"] < 0.20


def test_gateway_timeout_high_probability():
    gw_txn = {
        "amount": 800.0,
        "payment_method": "UPI",
        "failure_code": "GATEWAY_TIMEOUT",
        "failure_category": "TEMPORARY",
        "risk_score": 0.02,
        "customer_success_rate": 0.96,
        "customer_transaction_count": 40,
    }
    result = predict_recovery_probability(gw_txn)
    assert result["probability"] > 0.50


def test_duplicate_payment_low_probability():
    dup_txn = {
        "amount": 1200.0,
        "payment_method": "UPI",
        "failure_code": "DUPLICATE_PAYMENT",
        "failure_category": "DUPLICATE",
    }
    result = predict_recovery_probability(dup_txn)
    assert result["probability"] < 0.20


def test_singleton_accessor():
    inst1 = RecoveryPredictor.get_instance()
    inst2 = RecoveryPredictor.get_instance()
    assert inst1 is inst2
