from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.audit_trail import AuditEvent, AuditTrail
from backend.app.main import app
from backend.app.orchestrator import AgentTools, RecoveryOrchestrator
from backend.app.policy_engine import PolicyEngine
from backend.app.simulator import PaymentSimulator

client = TestClient(app)


@pytest.fixture
def audit_trail():
    trail = AuditTrail.get_instance()
    trail.clear()
    return trail


def test_audit_trail_logging_and_all_sixteen_fields(audit_trail):
    """Ensure all required fields are recorded in the immutable audit event."""
    evt = audit_trail.log_event(
        transaction_id="txn_audit_all_fields",
        event_type="ACTION_SELECTED",
        actor="ORCHESTRATOR",
        input_summary={"amount": 4500.0, "failure_code": "GATEWAY_TIMEOUT"},
        root_cause={"category": "TEMPORARY", "reason": "Network latency"},
        recovery_probability=0.82,
        candidate_actions=[{"action": "RETRY_PAYMENT", "expected_recovery_value": 3690.0}],
        selected_action="RETRY_PAYMENT",
        expected_value=3690.0,
        policy_result="ALLOW",
        policy_rule="POL-000",
        execution_result={"status": "SUCCESS"},
        revenue_recovered=4500.0,
        model_version="v1.2.0",
        agent_version="v1.0.0",
    )

    assert isinstance(evt, AuditEvent)
    data = evt.to_dict()

    required_fields = [
        "audit_id",
        "transaction_id",
        "timestamp",
        "event_type",
        "actor",
        "input_summary",
        "root_cause",
        "recovery_probability",
        "candidate_actions",
        "selected_action",
        "expected_value",
        "policy_result",
        "policy_rule",
        "execution_result",
        "revenue_recovered",
        "model_version",
        "agent_version",
        "hash",
    ]

    for f in required_fields:
        assert f in data, f"Missing required audit field: {f}"

    assert data["transaction_id"] == "txn_audit_all_fields"
    assert data["selected_action"] == "RETRY_PAYMENT"
    assert data["revenue_recovered"] == 4500.0
    assert data["model_version"] == "v1.2.0"
    assert data["agent_version"] == "v1.0.0"


def test_chronological_timeline_ordering(audit_trail):
    """Audit events must be returned in strict chronological order."""
    txn_id = "txn_chrono_test"

    audit_trail.log_event(txn_id, "PAYMENT_FAILED", timestamp="2026-09-03T10:00:00Z")
    audit_trail.log_event(txn_id, "ROOT_CAUSE_IDENTIFIED", timestamp="2026-09-03T10:00:02Z")
    audit_trail.log_event(txn_id, "RECOVERY_PREDICTED", timestamp="2026-09-03T10:00:04Z")
    audit_trail.log_event(txn_id, "POLICY_CHECKED", timestamp="2026-09-03T10:00:06Z")
    audit_trail.log_event(txn_id, "ACTION_SELECTED", timestamp="2026-09-03T10:00:08Z")
    audit_trail.log_event(txn_id, "ACTION_EXECUTED", timestamp="2026-09-03T10:00:10Z")
    audit_trail.log_event(txn_id, "PAYMENT_RECOVERED", timestamp="2026-09-03T10:00:12Z")

    timeline = audit_trail.get_timeline(txn_id)
    assert len(timeline) == 7

    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps)

    types = [e["event_type"] for e in timeline]
    assert types == [
        "PAYMENT_FAILED",
        "ROOT_CAUSE_IDENTIFIED",
        "RECOVERY_PREDICTED",
        "POLICY_CHECKED",
        "ACTION_SELECTED",
        "ACTION_EXECUTED",
        "PAYMENT_RECOVERED",
    ]


def test_all_example_event_types_supported(audit_trail):
    """Test that all required example event types can be recorded."""
    txn_id = "txn_example_events"
    example_types = [
        "PAYMENT_FAILED",
        "ROOT_CAUSE_IDENTIFIED",
        "RECOVERY_PREDICTED",
        "POLICY_CHECKED",
        "ACTION_SELECTED",
        "ACTION_EXECUTED",
        "PAYMENT_RECOVERED",
        "RECOVERY_FAILED",
        "ESCALATED",
        "STOPPED",
    ]

    for et in example_types:
        audit_trail.log_event(txn_id, et)

    timeline = audit_trail.get_timeline(txn_id)
    recorded_types = {e["event_type"] for e in timeline}
    for et in example_types:
        assert et in recorded_types


def test_every_denied_action_logged(audit_trail):
    """Every denied action must be logged with policy result and rule ID."""
    policy_engine = PolicyEngine()
    event = {
        "transaction_id": "txn_denied_audit_test",
        "status": "SUCCESS",
        "action": "RETRY_PAYMENT",
    }
    decision = policy_engine.evaluate(event)
    assert decision.allowed is False

    timeline = audit_trail.get_timeline("txn_denied_audit_test")
    assert len(timeline) >= 1
    denial_entry = timeline[-1]
    assert denial_entry["policy_result"] == "DENY"
    assert denial_entry["policy_rule"] == "POL-001"
    assert denial_entry["actor"] == "POLICY_ENGINE"


def test_every_successful_recovery_logged(audit_trail):
    """Every successful recovery must be logged with revenue_recovered amount."""
    sim = PaymentSimulator(seed=42)
    tools = AgentTools(simulator=sim)
    orch = RecoveryOrchestrator(tools=tools)

    event = {
        "transaction_id": "txn_success_audit_test",
        "amount": 3200.0,
        "failure_code": "GATEWAY_TIMEOUT",
        "payment_method": "UPI",
    }
    res = orch.run(event)
    assert res["monitoring_outcome"] == "RECOVERED"

    timeline = audit_trail.get_timeline("txn_success_audit_test")
    recovered_events = [e for e in timeline if e["event_type"] == "PAYMENT_RECOVERED"]
    assert len(recovered_events) >= 1
    assert recovered_events[0]["revenue_recovered"] == 3200.0


def test_tamper_evident_cryptographic_chain(audit_trail):
    """Cryptographic hash chain validates timeline integrity and detects tampering."""
    txn_id = "txn_tamper_test"
    audit_trail.log_event(txn_id, "PAYMENT_FAILED")
    audit_trail.log_event(txn_id, "POLICY_CHECKED")
    audit_trail.log_event(txn_id, "ACTION_SELECTED", selected_action="RETRY_PAYMENT")

    # Initial chain must be cryptographically valid
    assert audit_trail.verify_integrity(txn_id) is True

    # Tamper with an event in the chain
    events = audit_trail._by_transaction[txn_id]
    events[1].policy_result = "TAMPERED_ALLOW"  # Illegitimately altered field

    # Integrity verification must detect tampering and return False
    assert audit_trail.verify_integrity(txn_id) is False


def test_api_audit_endpoint(audit_trail):
    """GET /api/audit/{transaction_id} returns chronological timeline."""
    txn_id = "txn_api_audit_timeline"
    audit_trail.log_event(txn_id, "PAYMENT_FAILED", input_summary={"amount": 1800.0})
    audit_trail.log_event(txn_id, "ACTION_SELECTED", selected_action="RETRY_PAYMENT")
    audit_trail.log_event(txn_id, "PAYMENT_RECOVERED", revenue_recovered=1800.0)

    response = client.get(f"/api/audit/{txn_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["transaction_id"] == txn_id
    assert data["count"] == 3
    assert data["verified_integrity"] is True
    assert len(data["events"]) == 3
    assert data["events"][0]["event_type"] == "PAYMENT_FAILED"
    assert data["events"][2]["event_type"] == "PAYMENT_RECOVERED"
    assert data["events"][2]["revenue_recovered"] == 1800.0
