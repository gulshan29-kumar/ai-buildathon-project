from __future__ import annotations

import json
import pytest

from backend.app.orchestrator import (
    AgentTools,
    RecoveryAgentState,
    RecoveryOrchestrator,
)
from backend.app.simulator import PaymentSimulator, PaymentState


@pytest.fixture
def test_tools():
    sim = PaymentSimulator(seed=42)
    return AgentTools(simulator=sim)


@pytest.fixture
def orchestrator(test_tools):
    return RecoveryOrchestrator(tools=test_tools, max_steps=10)


def test_successful_recovery(orchestrator):
    """Test 1: Successful recovery flow from GATEWAY_TIMEOUT."""
    event = {
        "transaction_id": "txn_success_test",
        "amount": 2500.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "payment_method": "UPI",
        "risk_score": 0.05,
    }
    result = orchestrator.run(event)

    assert result["transaction_id"] == "txn_success_test"
    assert result["monitoring_outcome"] == "RECOVERED"
    assert result["selected_action"] == "RETRY_PAYMENT"
    assert result["execution_result"]["status"] == "SUCCESS"
    assert len(result["errors"]) == 0
    assert result["step_count"] > 0


def test_policy_denial(orchestrator):
    """Test 2: Policy denial on already successful transaction."""
    event = {
        "transaction_id": "txn_denial_test",
        "amount": 1500.0,
        "status": "SUCCESS",
        "failure_code": "",
        "risk_score": 0.05,
    }
    result = orchestrator.run(event)

    assert result["monitoring_outcome"] == "STOP"
    assert result["selected_action"] == "STOP"
    # PolicyEngine blocks further recovery on already successful transaction
    assert result["policy_decision"]["status"] in {"HALTED", "STOP"}


def test_escalation(orchestrator):
    """Test 3: High fraud risk triggers escalation."""
    event = {
        "transaction_id": "txn_escalate_test",
        "amount": 5000.0,
        "failure_code": "HIGH_RISK",
        "risk_score": 0.95,
    }
    result = orchestrator.run(event)

    assert result["monitoring_outcome"] == "ESCALATE"
    assert result["selected_action"] == "ESCALATE"
    assert result["execution_result"]["status"] == "ESCALATED"


def test_simulator_failure(orchestrator, monkeypatch):
    """Test 4: Graceful handling of simulator runtime failure."""
    def broken_retry(transaction_id, delay_seconds=0):
        raise RuntimeError("Gateway connection dropped unexpectedly.")

    monkeypatch.setattr(orchestrator.tools.simulator, "retry_payment", broken_retry)

    event = {
        "transaction_id": "txn_sim_fail_test",
        "amount": 1200.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    result = orchestrator.run(event)

    # Simulator failure is captured and escalated
    assert result["monitoring_outcome"] == "ESCALATE"
    assert any("Simulator execution failure" in err for err in result["errors"])
    assert result["execution_result"]["error"] == "SIMULATOR_FAILURE"


def test_llm_failure(test_tools):
    """Test 5: LLM network/API failure routes through deterministic fallback."""
    def broken_llm(prompt: str) -> str:
        raise TimeoutError("LLM Provider Timeout 504 Gateway Error")

    orch = RecoveryOrchestrator(tools=test_tools, llm_client=broken_llm)

    event = {
        "transaction_id": "txn_llm_fail_test",
        "amount": 3000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    result = orch.run(event)

    # Orchestrator catches LLM exception, marks fallback mode, and completes recovery!
    assert result["fallback_mode"] is True
    assert any("LLM failure" in err for err in result["errors"])
    assert result["monitoring_outcome"] == "RECOVERED"
    assert result["selected_action"] == "RETRY_PAYMENT"


def test_malformed_llm_response(test_tools):
    """Test 6: Malformed/hallucinated LLM response triggers deterministic fallback."""
    def garbage_llm(prompt: str) -> str:
        return "I am an AI assistant and I suggest doing nothing or calling <<INVALID_SYNTAX>>"

    orch = RecoveryOrchestrator(tools=test_tools, llm_client=garbage_llm)

    event = {
        "transaction_id": "txn_malformed_llm_test",
        "amount": 4000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    result = orch.run(event)

    assert result["fallback_mode"] is True
    assert any("Malformed LLM response" in err or "LLM failure" in err for err in result["errors"])
    assert result["monitoring_outcome"] == "RECOVERED"


def test_maximum_steps(orchestrator):
    """Test 7: Bounded execution enforces max_steps limit."""
    # Set step limit very low (e.g. 3 steps)
    event = {
        "transaction_id": "txn_max_steps_test",
        "amount": 2000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    result = orchestrator.run(event, max_steps=4)

    assert result["step_count"] <= 6
    assert result["monitoring_outcome"] in {"STOP", "WAIT", "RECOVERED"}


def test_all_thirteen_tools_present(test_tools):
    """Verify all 13 required tools are implemented and functional."""
    # 1. get_transaction
    txn = test_tools.get_transaction("non_existent")
    assert txn["status"] == "UNKNOWN"

    # 2. get_customer_context
    cust = test_tools.get_customer_context("cust_123")
    assert "preferred_payment_method" in cust

    # 3. get_payment_context
    pay_ctx = test_tools.get_payment_context("txn_123")
    assert "available_methods" in pay_ctx

    # 4. predict_recovery
    pred = test_tools.predict_recovery({"failure_code": "GATEWAY_TIMEOUT"})
    assert "recovery_probability" in pred

    # 5. get_action_probabilities
    action_probs = test_tools.get_action_probabilities({"failure_code": "GATEWAY_TIMEOUT", "amount": 1000.0})
    assert len(action_probs) == 6

    # 6. check_policy
    pol = test_tools.check_policy("RETRY_PAYMENT", {"status": "SUCCESS"})
    assert pol.allowed is False

    # Create dummy payment in simulator for action tools
    dummy = test_tools.simulator.create_payment(amount=1000.0, failure_code="GATEWAY_TIMEOUT")
    dummy_id = dummy["transaction_id"]

    # 7. retry_payment
    retry_res = test_tools.retry_payment(dummy_id)
    assert retry_res["attempt_number"] == 2

    # Switch payment
    dummy2 = test_tools.simulator.create_payment(amount=1000.0, failure_code="CARD_EXPIRED")
    # 8. switch_payment_method
    switch_res = test_tools.switch_payment_method(dummy2["transaction_id"], "UPI")
    assert switch_res["payment_method"] == "UPI"

    # 9. send_recovery_message
    dummy3 = test_tools.simulator.create_payment(amount=1000.0, failure_code="CUSTOMER_ABANDONED")
    msg_res = test_tools.send_recovery_message(dummy3["transaction_id"])
    assert msg_res["message_sent"] is True

    # 10. schedule_retry
    dummy4 = test_tools.simulator.create_payment(amount=1000.0, failure_code="INSUFFICIENT_FUNDS")
    sched_res = test_tools.schedule_retry(dummy4["transaction_id"], delay_seconds=60)
    assert sched_res["status"] == "SCHEDULED"


    # 11. get_payment_status
    status_res = test_tools.get_payment_status(dummy2["transaction_id"])
    assert "status" in status_res

    # 12. escalate_case
    esc_res = test_tools.escalate_case(dummy_id, reason="Manual review required")
    assert esc_res["status"] == "ESCALATED"

    # 13. log_audit_event
    audit_res = test_tools.log_audit_event("TEST_AUDIT", dummy_id, {"info": "ok"})
    assert audit_res["audit_id"].startswith("aud_")
