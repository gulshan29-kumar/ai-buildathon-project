from __future__ import annotations

import concurrent.futures
import threading
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app.action_predictor import ActionRecoveryPredictor
from backend.app.decision_engine import DecisionEngine
from backend.app.failure_handler import (
    AgentTimeoutError,
    AlreadySuccessfulPaymentError,
    ConcurrentRecoveryError,
    ConcurrentRecoveryManager,
    DatabaseUnavailableError,
    InvalidPaymentMethodError,
    MalformedEventError,
    PendingPaymentUncertainStateError,
    SafeRecoveryGuard,
    SimulatorExecutionError,
    TransactionNotFoundError,
    UncertainPaymentStateError,
    get_concurrent_recovery_manager,
)
from backend.app.main import app, orchestrator, simulator
from backend.app.orchestrator import AgentTools, RecoveryOrchestrator
from backend.app.policy_engine import PolicyEngine
from backend.app.simulator import PaymentSimulator, PolicyBlockedExecutionError


@pytest.fixture
def client():
    return TestClient(app)


# --- 1. LLM Unavailable ---

def test_llm_unavailable_deterministic_fallback():
    """Scenario 1: When LLM client is down/unavailable, orchestrator gracefully falls back to deterministic engine."""
    def failing_llm(prompt: str) -> str:
        raise ConnectionError("LLM provider endpoint connection timed out (HTTP 503)")

    sim = PaymentSimulator(seed=101)
    pe = PolicyEngine()
    tools = AgentTools(simulator=sim, policy_engine=pe)
    agent = RecoveryOrchestrator(tools=tools, llm_client=failing_llm)

    event = {
        "transaction_id": "txn_fail_llm_01",
        "amount": 2500.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.04,
    }
    result = agent.run(event)

    # Must not crash; must fall back to deterministic DecisionEngine
    assert result["fallback_mode"] is True
    assert any("LLM failure" in str(err) for err in result["errors"])
    assert result["selected_action"] in ("RETRY_PAYMENT", "SCHEDULE_RETRY")
    assert result["monitoring_outcome"] in ("RECOVERED", "WAIT", "STOP")


# --- 2. Database Unavailable ---

def test_database_unavailable_safe_rejection(client):
    """Scenario 2: When the database is down or disconnected, operations fail safely with HTTP 503."""
    from backend.app.database import get_db

    def failing_db():
        raise OperationalError("Connection refused: database server down", {}, None)

    app.dependency_overrides[get_db] = failing_db
    try:
        res = client.post("/api/events", json={
            "amount": 1500.0,
            "failure_code": "CARD_DECLINED",
            "transaction_id": "txn_db_fail_test",
        })
        assert res.status_code == 503
        data = res.json()
        assert data["error"] == "DATABASE_UNAVAILABLE"
    finally:
        app.dependency_overrides.pop(get_db, None)


# --- 3. Simulator Failure ---

def test_simulator_failure_halts_retries_and_escalates():
    """Scenario 3: When the payment simulator or gateway throws an unhandled error, retries are halted and state escalated."""
    sim = PaymentSimulator(seed=102)
    pe = PolicyEngine()
    tools = AgentTools(simulator=sim, policy_engine=pe)

    # Mock simulator retry to fail abruptly
    tools.simulator.retry_payment = MagicMock(side_effect=RuntimeError("Gateway connection dropped mid-transaction"))

    agent = RecoveryOrchestrator(tools=tools)
    event = {
        "transaction_id": "txn_sim_fail_test",
        "amount": 4000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    result = agent.run(event)

    # Failure marks payment state uncertain -> DO NOT RETRY -> ESCALATE
    assert result["uncertain_payment_state"] is True
    assert result["monitoring_outcome"] == "ESCALATE"
    assert result["execution_result"]["error"] == "SIMULATOR_FAILURE"


# --- 4. Malformed Event ---

def test_malformed_event_rejection():
    """Scenario 4: Malformed payloads (missing IDs, negative amounts, invalid types) are rejected with MalformedEventError."""
    # Missing transaction_id
    with pytest.raises(MalformedEventError):
        SafeRecoveryGuard.validate_event_payload({"amount": 100.0})

    # Negative amount
    with pytest.raises(MalformedEventError):
        SafeRecoveryGuard.validate_event_payload({"transaction_id": "txn_bad_amt", "amount": -50.0})

    # Excessive amount exceeding platform threshold
    with pytest.raises(MalformedEventError):
        SafeRecoveryGuard.validate_event_payload({"transaction_id": "txn_too_high", "amount": 999_999_999.0})

    # Non-dictionary payload
    with pytest.raises(MalformedEventError):
        SafeRecoveryGuard.validate_event_payload("not_a_dict")


# --- 5. Missing Customer ---

def test_missing_customer_safe_default_context():
    """Scenario 5: When customer profile is missing, safe conservative fallback context is applied with communication blocked."""
    tools = AgentTools()
    cust_ctx = tools.get_customer_context("missing_cust_888")

    assert cust_ctx["is_fallback_profile"] is True
    assert cust_ctx["communication_allowed"] is False
    assert cust_ctx["communication_opt_out"] is True
    assert cust_ctx["dnd"] is True
    assert cust_ctx["risk_score"] == 0.50


# --- 6. Missing Transaction ---

def test_missing_transaction_returns_404(client):
    """Scenario 6: Recovery request on non-existent transaction returns HTTP 404."""
    res = client.post("/api/recovery/run/txn_non_existent_999999")
    assert res.status_code == 404
    data = res.json()
    assert data["error"] == "TRANSACTION_NOT_FOUND"


# --- 7. Duplicate Event ---

def test_duplicate_event_deduplication(client):
    """Scenario 7: Duplicate events are deduplicated via IdempotencyManager with cached response."""
    idem_key = "idem_dup_event_test_101"
    payload = {
        "transaction_id": "txn_dup_event_101",
        "amount": 1800.0,
        "failure_code": "BANK_UNAVAILABLE",
    }
    headers = {"Idempotency-Key": idem_key}

    res1 = client.post("/api/events", json=payload, headers=headers)
    assert res1.status_code == 201

    # Second call returns identical cached response
    res2 = client.post("/api/events", json=payload, headers=headers)
    assert res2.status_code == 201
    assert res1.json()["event_id"] == res2.json()["event_id"]


# --- 8. Duplicate Payment ---

def test_duplicate_payment_policy_denial():
    """Scenario 8: Failure code DUPLICATE_PAYMENT is strictly blocked by Rule POL-002."""
    pe = PolicyEngine()
    event = {
        "transaction_id": "txn_dup_payment_test",
        "status": "FAILED",
        "failure_code": "DUPLICATE_PAYMENT",
        "action": "RETRY_PAYMENT",
    }
    decision = pe.evaluate(event)
    assert decision.allowed is False
    assert decision.rule_id == "POL-002"
    assert decision.action == "STOP"


# --- 9. Successful Transaction Retried ---

def test_successful_transaction_cannot_be_retried(client):
    """Scenario 9: Attempting recovery on a settled SUCCESS payment is strictly blocked with HTTP 400."""
    sim = simulator
    sim.payments["txn_settled_test"] = {
        "transaction_id": "txn_settled_test",
        "amount": 5000.0,
        "status": "SUCCESS",
        "failure_code": None,
        "risk_score": 0.02,
    }

    res = client.post("/api/recovery/run/txn_settled_test")
    assert res.status_code == 400
    data = res.json()
    assert data["error"] == "PAYMENT_ALREADY_SUCCESSFUL"


# --- 10. Pending Transaction (Uncertain Payment State) ---

def test_pending_transaction_uncertain_state_prohibits_retry(client):
    """Scenario 10: If payment state is uncertain/pending, automated retry is prohibited (Rule POL-007, HTTP 409)."""
    sim = simulator
    sim.payments["txn_pending_test"] = {
        "transaction_id": "txn_pending_test",
        "amount": 7500.0,
        "status": "PENDING",
        "failure_code": "PAYMENT_PENDING",
        "risk_score": 0.04,
    }

    res = client.post("/api/recovery/run/txn_pending_test")
    assert res.status_code == 409
    data = res.json()
    assert data["error"] == "PAYMENT_PENDING_WAIT"

    # Also verify orchestrator internal invariant: "If payment state is uncertain: DO NOT RETRY"
    agent = RecoveryOrchestrator()
    state = agent.run({
        "transaction_id": "txn_pending_test2",
        "amount": 7500.0,
        "status": "PENDING",
        "failure_code": "PAYMENT_PENDING",
    })
    assert state["uncertain_payment_state"] is True
    assert state["execution_result"]["action"] == "WAIT_AND_POLL"
    assert state["monitoring_outcome"] == "WAIT"


# --- 11. Agent Timeout ---

def test_agent_timeout_aborts_safely():
    """Scenario 11: Agent execution aborts safely and logs structured error when execution timeout is reached."""
    # Set execution timeout to near zero to trigger timeout check
    agent = RecoveryOrchestrator(execution_timeout=0.00001)

    event = {
        "transaction_id": "txn_timeout_test",
        "amount": 2000.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    # Artificially delay action analysis
    orig_node_analysis = agent.node_action_analysis
    def delayed_analysis(state):
        time.sleep(0.01)
        return orig_node_analysis(state)
    agent.node_action_analysis = delayed_analysis

    result = agent.run(event)
    assert any("timeout" in err.lower() for err in result["errors"])
    assert result["monitoring_outcome"] == "STOP"


# --- 12. Invalid LLM Output ---

def test_invalid_llm_output_deterministic_fallback():
    """Scenario 12: Malformed or hallucinated LLM JSON degrades seamlessly to deterministic DecisionEngine."""
    sim = PaymentSimulator(seed=103)
    pe = PolicyEngine()
    tools = AgentTools(simulator=sim, policy_engine=pe)

    # Returns invalid non-JSON output
    malformed_llm = MagicMock(return_value="```json\n{ invalid_json: true, action: NOT_AN_ACTION }\n```")
    agent = RecoveryOrchestrator(tools=tools, llm_client=malformed_llm)

    event = {
        "transaction_id": "txn_malformed_llm_test",
        "amount": 3200.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "risk_score": 0.05,
    }
    result = agent.run(event)

    # Must gracefully fall back to deterministic decision engine
    assert result["fallback_mode"] is True
    assert result["selected_action"] in ("RETRY_PAYMENT", "SCHEDULE_RETRY")


# --- 13. Policy Denial ---

def test_policy_denial_respects_guardrails():
    """Scenario 13: Actions denied by safety policy (e.g. POL-003 fraud threshold) are never executed."""
    sim = PaymentSimulator(seed=104)
    pe = PolicyEngine()
    tools = AgentTools(simulator=sim, policy_engine=pe)
    agent = RecoveryOrchestrator(tools=tools)

    # Register high-risk transaction
    sim.payments["txn_fraud_denied"] = {
        "transaction_id": "txn_fraud_denied",
        "amount": 60000.0,
        "status": "FAILED",
        "failure_code": "HIGH_RISK",
        "risk_score": 0.96,
        "attempt_count": 1,
    }

    result = agent.run(sim.payments["txn_fraud_denied"])
    assert result["selected_action"] == "ESCALATE"
    assert result["monitoring_outcome"] == "ESCALATE"


# --- 14. Concurrent Recovery Request ---

def test_concurrent_recovery_returns_409_conflict():
    """Scenario 14: Simultaneous recovery attempts on the same transaction are serialized and return HTTP 409."""
    mgr = get_concurrent_recovery_manager()
    txn_id = "txn_concurrent_lock_test"

    # Acquire lock in thread 1
    mgr.acquire(txn_id)
    try:
        # Second acquire attempt must raise ConcurrentRecoveryError
        with pytest.raises(ConcurrentRecoveryError) as exc_info:
            mgr.acquire(txn_id)
        assert exc_info.value.status_code == 409
        assert "already in progress" in str(exc_info.value)
    finally:
        mgr.release(txn_id)

    # Once released, lock can be acquired again
    assert mgr.is_active(txn_id) is False


# --- 15. Invalid Payment Method ---

def test_invalid_payment_method_rejection(client):
    """Scenario 15: Specifying an unauthorized payment method raises InvalidPaymentMethodError (HTTP 400)."""
    # Test validator directly
    with pytest.raises(InvalidPaymentMethodError):
        SafeRecoveryGuard.validate_payment_method("BITCOIN")

    with pytest.raises(InvalidPaymentMethodError):
        SafeRecoveryGuard.validate_payment_method("GOLD_COINS")

    # Test via API
    res = client.post("/api/simulate/switch", json={
        "transaction_id": "txn_rr_101",
        "new_payment_method": "CRYPTOCURRENCY",
    })
    assert res.status_code == 400
    data = res.json()
    assert data["error"] == "INVALID_PAYMENT_METHOD"
