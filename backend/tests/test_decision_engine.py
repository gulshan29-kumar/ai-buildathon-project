from __future__ import annotations

import pytest

from backend.app.decision_engine import (
    DecisionEngine,
    RecoveryCandidate,
    RecoveryDecision,
)


@pytest.fixture
def decision_engine():
    return DecisionEngine()


def test_user_example_ranking_10000(decision_engine):
    """Verifies user example: ₹10,000 with Retry=0.78 (₹7,800), Switch=0.65 (₹6,500), Message=0.31 (₹3,100)."""
    txn = {
        "transaction_id": "txn_example_10k",
        "amount": 10000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "status": "FAILED",
        "risk_score": 0.05,
    }
    action_probs = {
        "RETRY_PAYMENT": 0.78,
        "SWITCH_PAYMENT_METHOD": 0.65,
        "SEND_RECOVERY_MESSAGE": 0.31,
        "SCHEDULE_RETRY": 0.40,
        "ESCALATE": 0.15,
        "STOP": 0.0,
    }

    decision = decision_engine.decide(
        transaction=txn,
        action_probabilities=action_probs,
    )

    assert decision.selected_action == "RETRY_PAYMENT"
    assert decision.recovery_probability == 0.78
    assert decision.expected_recovery_value == 7800.0
    assert decision.fallback_action == "SWITCH_PAYMENT_METHOD"

    # Verify candidates list contains expected values
    cands_map = {c.action: c for c in decision.candidates}
    assert cands_map["RETRY_PAYMENT"].expected_recovery_value == 7800.0
    assert cands_map["SWITCH_PAYMENT_METHOD"].expected_recovery_value == 6500.0
    assert cands_map["SEND_RECOVERY_MESSAGE"].expected_recovery_value == 3100.0


def test_edge_case_1_already_successful(decision_engine):
    txn = {
        "transaction_id": "txn_succ_1",
        "amount": 5000.0,
        "status": "SUCCESS",
    }
    decision = decision_engine.decide(transaction=txn)
    assert decision.selected_action == "STOP"
    assert decision.expected_recovery_value == 0.0
    assert decision.policy_status == "HALTED"
    assert "already successful" in decision.reasoning_summary.lower()


def test_edge_case_2_pending_payment(decision_engine):
    txn = {
        "transaction_id": "txn_pend_1",
        "amount": 2500.0,
        "status": "PENDING",
    }
    decision = decision_engine.decide(transaction=txn)
    assert decision.selected_action == "WAIT_AND_POLL"
    assert decision.expected_recovery_value == 0.0
    assert decision.policy_status == "WAIT"


def test_edge_case_3_duplicate_payment(decision_engine):
    txn = {
        "transaction_id": "txn_dup_1",
        "amount": 3000.0,
        "failure_code": "DUPLICATE_PAYMENT",
    }
    decision = decision_engine.decide(transaction=txn)
    assert decision.selected_action == "STOP"
    assert decision.expected_recovery_value == 0.0
    assert decision.policy_status == "HALTED"
    assert "duplicate payment" in decision.reasoning_summary.lower()


def test_edge_case_4_high_risk(decision_engine):
    txn = {
        "transaction_id": "txn_fraud_1",
        "amount": 15000.0,
        "failure_code": "HIGH_RISK",
        "risk_score": 0.95,
    }
    decision = decision_engine.decide(transaction=txn)
    assert decision.selected_action in {"ESCALATE", "STOP"}
    # Automatic actions (Retry, Switch, Message, Schedule) must not be chosen
    assert decision.selected_action not in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD", "SEND_RECOVERY_MESSAGE", "SCHEDULE_RETRY"}


def test_edge_case_5_maximum_retries(decision_engine):
    txn = {
        "transaction_id": "txn_max_retries",
        "amount": 6000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "attempt_number": 3,  # Already attempted twice
        "risk_score": 0.05,
    }
    action_probs = {
        "RETRY_PAYMENT": 0.85,
        "SWITCH_PAYMENT_METHOD": 0.70,
        "SCHEDULE_RETRY": 0.60,
    }
    decision = decision_engine.decide(transaction=txn, action_probabilities=action_probs)
    # RETRY_PAYMENT is blocked by retry limit rule; engine must fall back to SWITCH_PAYMENT_METHOD
    assert decision.selected_action == "SWITCH_PAYMENT_METHOD"
    assert decision.expected_recovery_value == 4200.0


def test_edge_case_6_unsupported_payment_method(decision_engine):
    txn = {
        "transaction_id": "txn_only_upi",
        "amount": 4000.0,
        "payment_method": "UPI",
        "failure_code": "CARD_EXPIRED",
    }
    # Only UPI available, which is already the current method (no alternate method)
    decision = decision_engine.decide(
        transaction=txn,
        available_payment_methods=["UPI"],
        action_probabilities={"SWITCH_PAYMENT_METHOD": 0.80, "SEND_RECOVERY_MESSAGE": 0.50},
    )
    # SWITCH_PAYMENT_METHOD must be disqualified because no alternate method exists
    cands_map = {c.action: c for c in decision.candidates}
    assert cands_map["SWITCH_PAYMENT_METHOD"].permitted is False
    assert decision.selected_action != "SWITCH_PAYMENT_METHOD"


def test_edge_case_7_zero_probability(decision_engine):
    txn = {
        "transaction_id": "txn_zero_prob",
        "amount": 1000.0,
        "failure_code": "CARD_DECLINED",
    }
    # All candidate actions have 0 probability
    action_probs = {act: 0.0 for act in ["RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD", "SEND_RECOVERY_MESSAGE", "SCHEDULE_RETRY", "ESCALATE", "STOP"]}
    decision = decision_engine.decide(transaction=txn, action_probabilities=action_probs)
    assert decision.selected_action in {"STOP", "ESCALATE"}
    assert decision.expected_recovery_value == 0.0


def test_edge_case_8_equal_probability_tie_breaker(decision_engine):
    txn = {
        "transaction_id": "txn_tie",
        "amount": 5000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    # Both RETRY_PAYMENT and SWITCH_PAYMENT_METHOD have identical 0.70 probability (₹3,500 EV)
    action_probs = {
        "RETRY_PAYMENT": 0.70,
        "SWITCH_PAYMENT_METHOD": 0.70,
        "SEND_RECOVERY_MESSAGE": 0.30,
        "SCHEDULE_RETRY": 0.20,
        "ESCALATE": 0.10,
        "STOP": 0.0,
    }
    decision = decision_engine.decide(transaction=txn, action_probabilities=action_probs)
    # Priority order places RETRY_PAYMENT ahead of SWITCH_PAYMENT_METHOD
    assert decision.selected_action == "RETRY_PAYMENT"
    assert decision.expected_recovery_value == 3500.0


def test_edge_case_9_missing_context(decision_engine):
    # Completely empty contexts should not throw an exception
    decision = decision_engine.decide(
        transaction={},
        customer_context=None,
        payment_context=None,
    )
    assert isinstance(decision, RecoveryDecision)
    assert decision.selected_action is not None
    assert decision.expected_recovery_value >= 0.0


def test_payment_context_fallback_and_retry_limits(decision_engine):
    # Transaction lacks amount/status, supplied via payment_context
    pay_ctx = {
        "order_id": "ord_ctx_999",
        "amount": 7500.0,
        "status": "FAILED",
        "failure_code": "GATEWAY_TIMEOUT",
        "previous_retry_count": 2,  # Reached limit
    }
    action_probs = {
        "RETRY_PAYMENT": 0.85,
        "SWITCH_PAYMENT_METHOD": 0.70,
        "SCHEDULE_RETRY": 0.50,
    }
    decision = decision_engine.decide(
        transaction={},
        payment_context=pay_ctx,
        action_probabilities=action_probs,
    )
    # Retry payment is blocked due to previous_retry_count=2, fallback to SWITCH_PAYMENT_METHOD
    assert decision.selected_action == "SWITCH_PAYMENT_METHOD"
    assert decision.expected_recovery_value == round(7500.0 * 0.70, 2)


def test_preferred_payment_method_recommendation(decision_engine):
    txn = {
        "transaction_id": "txn_pref_method",
        "amount": 3000.0,
        "failure_code": "CARD_EXPIRED",
        "payment_method": "CARD",
    }
    cust = {
        "customer_id": "cust_123",
        "preferred_payment_method": "UPI",
    }
    decision = decision_engine.decide(
        transaction=txn,
        customer_context=cust,
        available_payment_methods=["NETBANKING", "UPI", "WALLET"],
    )
    # Finding candidate for SWITCH_PAYMENT_METHOD
    cands_map = {c.action: c for c in decision.candidates}
    switch_cand = cands_map["SWITCH_PAYMENT_METHOD"]
    assert switch_cand.permitted is True
    assert switch_cand.parameters["suggested_method"] == "UPI"


def test_no_llm_dependency():
    """Verify that DecisionEngine operates purely deterministically without any LLM."""
    import inspect
    from backend.app.decision_engine import DecisionEngine

    source = inspect.getsource(DecisionEngine)
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
    assert "langchain" not in source.lower()
    assert "prompt" not in source.lower()

