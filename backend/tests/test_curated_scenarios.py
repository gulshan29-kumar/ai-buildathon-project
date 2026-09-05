from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.curated_scenarios import (
    CURATED_SCENARIOS_SPEC,
    CuratedScenarioEngine,
    curated_scenario_engine,
)
from backend.app.main import app

client = TestClient(app)


def test_curated_scenarios_count_and_spec():
    """Verify exactly 8 curated scenarios are registered with valid specs."""
    assert len(CURATED_SCENARIOS_SPEC) >= 8
    expected_scenarios = [
        "scenario_gateway_timeout",
        "scenario_insufficient_funds",
        "scenario_expired_card",
        "scenario_checkout_abandonment",
        "scenario_high_risk",
        "scenario_pending_payment",
        "scenario_duplicate_payment",
        "scenario_order_creation_failure",
    ]
    registered_ids = [s["scenario_id"] for s in CURATED_SCENARIOS_SPEC]
    for exp in expected_scenarios:
        assert exp in registered_ids


def test_engine_summaries():
    """Verify get_all_summaries returns all 8 scenarios with required metadata."""
    summaries = curated_scenario_engine.get_all_summaries()
    assert len(summaries) == 8
    for s in summaries:
        assert "scenario_id" in s
        assert "title" in s
        assert "category" in s
        assert "amount" in s
        assert "is_executed" in s
        assert "recovered" in s
        assert "selected_action" in s


def test_all_8_scenarios_have_all_9_required_stages():
    """Verify each scenario produces all 9 stages required by Phase 25."""
    required_stages = [
        "input",
        "root_cause",
        "ml_prediction",
        "candidate_actions",
        "policy",
        "agent_decision",
        "simulator_result",
        "revenue_recovered",
        "audit_trail",
    ]

    for spec in CURATED_SCENARIOS_SPEC:
        sc_id = spec["scenario_id"]
        trace = curated_scenario_engine.get_scenario_trace(sc_id)
        assert trace is not None, f"Trace missing for {sc_id}"

        for stage in required_stages:
            assert stage in trace, f"Stage '{stage}' missing from scenario '{sc_id}'"

        # Verify Stage 1: input
        inp = trace["input"]
        assert inp["amount"] == spec["amount"]
        assert inp["payment_method"] == spec["payment_method"]
        assert inp["failure_code"] == spec["failure_code"]

        # Verify Stage 2: root_cause
        rc = trace["root_cause"]
        assert "category" in rc
        assert "diagnosed_cause" in rc
        assert "confidence" in rc

        # Verify Stage 3: ml_prediction
        ml = trace["ml_prediction"]
        assert "recovery_probability" in ml
        assert "expected_value" in ml
        assert "feature_contributions" in ml
        assert 0.0 <= ml["recovery_probability"] <= 1.0

        # Verify Stage 4: candidate_actions
        cands = trace["candidate_actions"]
        assert isinstance(cands, list) and len(cands) >= 1
        for cand in cands:
            assert "action" in cand
            assert "probability" in cand
            assert "permitted_by_policy" in cand

        # Verify Stage 5: policy
        pol = trace["policy"]
        assert "decision" in pol
        assert "rule_id" in pol
        assert "reason" in pol
        assert "rules_evaluated" in pol

        # Verify Stage 6: agent_decision
        agent = trace["agent_decision"]
        assert "selected_action" in agent
        assert "reasoning" in agent
        assert "execution_parameters" in agent
        assert agent["selected_action"] == spec["expected_action"]

        # Verify Stage 7: simulator_result
        sim = trace["simulator_result"]
        assert "execution_status" in sim
        assert "from_state" in sim
        assert "to_state" in sim
        assert "gateway_response" in sim

        # Verify Stage 8: revenue_recovered
        rev = trace["revenue_recovered"]
        assert "amount" in rev
        assert "recovered" in rev
        assert rev["recovered"] == spec["expected_recovered"]
        assert rev["amount"] == spec["expected_revenue"]

        # Verify Stage 9: audit_trail
        audit = trace["audit_trail"]
        assert "total_events" in audit
        assert audit["verified_integrity"] is True
        assert len(audit["events"]) >= 5


def test_determinism_and_reproducibility():
    """Verify repeated executions yield exactly the same deterministic outcomes."""
    engine = CuratedScenarioEngine(seed=999)
    run1 = engine.run_scenario("scenario_gateway_timeout")
    run2 = engine.run_scenario("scenario_gateway_timeout")

    assert run1["agent_decision"]["selected_action"] == run2["agent_decision"]["selected_action"]
    assert run1["revenue_recovered"]["amount"] == run2["revenue_recovered"]["amount"]
    assert run1["revenue_recovered"]["recovered"] == run2["revenue_recovered"]["recovered"]
    assert run1["ml_prediction"]["recovery_probability"] == run2["ml_prediction"]["recovery_probability"]
    assert run1["simulator_result"]["execution_status"] == run2["simulator_result"]["execution_status"]


def test_api_scenarios_list():
    """Verify GET /api/scenarios endpoint."""
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert "scenarios" in data
    assert data["total"] == 8
    assert len(data["scenarios"]) == 8


def test_api_scenario_detail_and_not_found():
    """Verify GET /api/scenarios/{id} for valid and invalid scenario IDs."""
    res = client.get("/api/scenarios/scenario_gateway_timeout")
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_id"] == "scenario_gateway_timeout"
    assert "input" in data
    assert "audit_trail" in data

    res_404 = client.get("/api/scenarios/scenario_nonexistent_xyz")
    assert res_404.status_code == 404


def test_api_scenario_run_and_run_all():
    """Verify POST /api/scenarios/{id}/run and POST /api/scenarios/run-all endpoints."""
    res_run = client.post("/api/scenarios/scenario_expired_card/run")
    assert res_run.status_code == 200
    data = res_run.json()
    assert data["agent_decision"]["selected_action"] == "SWITCH_PAYMENT_METHOD"
    assert data["revenue_recovered"]["recovered"] is True

    res_all = client.post("/api/scenarios/run-all")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert all_data["total_scenarios"] == 8
    assert all_data["executed_count"] == 8
    assert len(all_data["traces"]) == 8


def test_api_scenarios_reset():
    """Verify POST /api/scenarios/reset endpoint."""
    res = client.post("/api/scenarios/reset")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "reset_successful"
    assert data["summary"]["total_scenarios"] == 8
