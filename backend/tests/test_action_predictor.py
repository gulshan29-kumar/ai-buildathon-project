from __future__ import annotations

import pytest

from backend.app.action_predictor import (
    SUPPORTED_ACTIONS,
    estimate_action_recovery,
    evaluate_all_actions,
)


def test_evaluate_all_actions_structure():
    txn = {
        "amount": 10000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    results = evaluate_all_actions(txn)
    assert len(results) == len(SUPPORTED_ACTIONS)

    action_names = {r["action"] for r in results}
    assert action_names == set(SUPPORTED_ACTIONS)

    for r in results:
        assert "action" in r
        assert "probability" in r
        assert "expected_recovery_value" in r
        assert 0.0 <= r["probability"] <= 1.0
        # Expected value must be amount * probability
        assert r["expected_recovery_value"] == round(txn["amount"] * r["probability"], 2)


def test_actions_have_distinct_probabilities():
    txn = {
        "amount": 5000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    results = evaluate_all_actions(txn)
    probs = [r["probability"] for r in results]
    # Check that not all probabilities are the same
    assert len(set(probs)) > 3


def test_gateway_timeout_retry_high_probability():
    txn = {
        "amount": 2000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.02,
        "customer_success_rate": 0.95,
    }
    res = estimate_action_recovery(txn, "RETRY_PAYMENT")
    assert res["probability"] >= 0.75
    assert res["expected_recovery_value"] >= 1500.0


def test_expired_card_retry_low_switch_high():
    txn = {
        "amount": 3500.0,
        "failure_code": "CARD_EXPIRED",
        "risk_score": 0.05,
    }
    retry_res = estimate_action_recovery(txn, "RETRY_PAYMENT")
    switch_res = estimate_action_recovery(txn, "SWITCH_PAYMENT_METHOD")

    assert retry_res["probability"] <= 0.05
    assert switch_res["probability"] >= 0.70
    assert switch_res["expected_recovery_value"] > retry_res["expected_recovery_value"]


def test_insufficient_funds_immediate_low_scheduled_higher():
    txn = {
        "amount": 4000.0,
        "failure_code": "INSUFFICIENT_FUNDS",
        "risk_score": 0.10,
    }
    retry_res = estimate_action_recovery(txn, "RETRY_PAYMENT")
    sched_res = estimate_action_recovery(txn, "SCHEDULE_RETRY")
    switch_res = estimate_action_recovery(txn, "SWITCH_PAYMENT_METHOD")

    assert retry_res["probability"] < 0.15
    assert sched_res["probability"] >= 0.45
    assert switch_res["probability"] >= 0.60


def test_abandoned_checkout_message_meaningful_probability():
    txn = {
        "amount": 1500.0,
        "failure_code": "CUSTOMER_ABANDONED",
        "risk_score": 0.05,
    }
    msg_res = estimate_action_recovery(txn, "SEND_RECOVERY_MESSAGE")
    retry_res = estimate_action_recovery(txn, "RETRY_PAYMENT")

    assert msg_res["probability"] >= 0.45
    assert retry_res["probability"] <= 0.10


def test_high_risk_automatic_recovery_blocked():
    txn = {
        "amount": 25000.0,
        "failure_code": "HIGH_RISK",
        "risk_score": 0.92,
    }
    for action in ["RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD", "SEND_RECOVERY_MESSAGE", "SCHEDULE_RETRY"]:
        res = estimate_action_recovery(txn, action)
        assert res["probability"] == 0.0
        assert res["expected_recovery_value"] == 0.0


def test_duplicate_payment_all_recovery_zero():
    txn = {
        "amount": 1200.0,
        "failure_code": "DUPLICATE_PAYMENT",
    }
    for action in SUPPORTED_ACTIONS:
        res = estimate_action_recovery(txn, action)
        assert res["probability"] == 0.0
        assert res["expected_recovery_value"] == 0.0


def test_stop_action_always_zero():
    txn = {"amount": 1000.0, "failure_code": "GATEWAY_TIMEOUT"}
    res = estimate_action_recovery(txn, "STOP")
    assert res["probability"] == 0.0
    assert res["expected_recovery_value"] == 0.0


def test_unsupported_action_raises():
    txn = {"amount": 1000.0}
    with pytest.raises(ValueError, match="Unsupported action"):
        estimate_action_recovery(txn, "INVALID_ACTION")


def test_predict_action_recovery_alias_equivalence():
    txn = {
        "amount": 2500.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    from backend.app.action_predictor import (
        predict_action_recovery,
        predict_all_action_recoveries,
    )

    single1 = estimate_action_recovery(txn, "RETRY_PAYMENT")
    single2 = predict_action_recovery(txn, "RETRY_PAYMENT")
    assert single1 == single2

    all1 = evaluate_all_actions(txn)
    all2 = predict_all_action_recoveries(txn)
    assert all1 == all2


def test_amount_edge_cases_handling():
    # String amount
    txn_str = {"amount": "4500.50", "failure_code": "GATEWAY_TIMEOUT"}
    res = estimate_action_recovery(txn_str, "RETRY_PAYMENT")
    assert res["expected_recovery_value"] == round(4500.50 * res["probability"], 2)

    # Zero amount
    txn_zero = {"amount": 0.0, "failure_code": "GATEWAY_TIMEOUT"}
    res_zero = estimate_action_recovery(txn_zero, "RETRY_PAYMENT")
    assert res_zero["expected_recovery_value"] == 0.0

    # Negative amount clamped
    txn_neg = {"amount": -500.0, "failure_code": "GATEWAY_TIMEOUT"}
    res_neg = estimate_action_recovery(txn_neg, "RETRY_PAYMENT")
    assert res_neg["expected_recovery_value"] == 0.0

    # Missing amount defaults to 0.0
    txn_none = {"failure_code": "GATEWAY_TIMEOUT"}
    res_none = estimate_action_recovery(txn_none, "RETRY_PAYMENT")
    assert res_none["expected_recovery_value"] == 0.0


def test_custom_synthetic_simulator_benchmarks_injection():
    from backend.app.action_predictor import ActionRecoveryPredictor

    custom_benchmarks = {
        "GATEWAY_TIMEOUT": {
            "RETRY_PAYMENT": 0.90,
            "SCHEDULE_RETRY": 0.70,
            "SWITCH_PAYMENT_METHOD": 0.40,
            "SEND_RECOVERY_MESSAGE": 0.30,
            "ESCALATE": 0.10,
            "STOP": 0.00,
        }
    }
    custom_predictor = ActionRecoveryPredictor(synthetic_benchmarks=custom_benchmarks)
    txn = {"amount": 1000.0, "failure_code": "GATEWAY_TIMEOUT", "risk_score": 0.0, "customer_success_rate": 0.70}
    res = custom_predictor.evaluate_action(txn, "RETRY_PAYMENT")
    assert res["probability"] == 0.90
    assert res["expected_recovery_value"] == 900.0


def test_deterministic_predictions():
    """Ensure that identical input transactions produce strictly identical, deterministic results."""
    txn = {
        "amount": 7800.0,
        "failure_code": "BANK_UNAVAILABLE",
        "risk_score": 0.12,
        "attempt_number": 1,
    }
    run1 = evaluate_all_actions(txn)
    run2 = evaluate_all_actions(txn)
    assert run1 == run2

