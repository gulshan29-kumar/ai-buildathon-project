import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.subscription_recovery import (
    SubscriptionAction,
    SubscriptionCustomerHistory,
    SubscriptionDecisionEngine,
    SubscriptionLifecycleState,
    SubscriptionRecoveryAgent,
    SubscriptionRecoveryPredictor,
    SubscriptionSimulator,
    SubscriptionState,
    SubscriptionStore,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_subscription_lifecycle_states():
    """Verifies all 7 required subscription lifecycle states exist and can be transitioned."""
    states = [
        SubscriptionLifecycleState.SUBSCRIPTION_CREATED,
        SubscriptionLifecycleState.PAYMENT_ATTEMPTED,
        SubscriptionLifecycleState.PAYMENT_FAILED,
        SubscriptionLifecycleState.RETRY_SCHEDULED,
        SubscriptionLifecycleState.PAYMENT_METHOD_CHANGED,
        SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED,
        SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED,
    ]
    assert len(states) == 7

    now = datetime.now(timezone.utc)
    sub = SubscriptionState(
        subscription_id="sub_test_states",
        customer_id="cust_t1",
        merchant_id="merch_1",
        plan_name="Enterprise Plus",
        renewal_amount=9999.0,
        current_state=SubscriptionLifecycleState.SUBSCRIPTION_CREATED,
        created_at=now,
        updated_at=now,
    )
    assert sub.current_state == SubscriptionLifecycleState.SUBSCRIPTION_CREATED

    # Attempt
    sub.current_state = SubscriptionLifecycleState.PAYMENT_ATTEMPTED
    assert sub.current_state == SubscriptionLifecycleState.PAYMENT_ATTEMPTED

    # Failed
    sub.current_state = SubscriptionLifecycleState.PAYMENT_FAILED
    assert sub.current_state == SubscriptionLifecycleState.PAYMENT_FAILED

    # Retry scheduled
    sub.current_state = SubscriptionLifecycleState.RETRY_SCHEDULED
    assert sub.current_state == SubscriptionLifecycleState.RETRY_SCHEDULED

    # Method changed
    sub.current_state = SubscriptionLifecycleState.PAYMENT_METHOD_CHANGED
    assert sub.current_state == SubscriptionLifecycleState.PAYMENT_METHOD_CHANGED

    # Recovered
    sub.current_state = SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED
    assert sub.current_state == SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED

    # Cancelled
    sub.current_state = SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED
    assert sub.current_state == SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED


def test_customer_history_impact_on_recovery_predictions():
    """Verifies customer tenure, consecutive renewals, and backup rails influence probabilities."""
    predictor = SubscriptionRecoveryPredictor()
    now = datetime.now(timezone.utc)

    # 1. Loyal subscriber with backup UPI AutoPay and expired card
    hist_loyal = SubscriptionCustomerHistory(
        customer_id="cust_loyal",
        tenure_months=18,
        consecutive_successful_renewals=15,
        lifetime_billing_volume=150000.0,
        past_decline_count=0,
        primary_payment_method="CARD",
        backup_payment_method="UPI_AUTOPAY",
        risk_score=0.01,
        dnd_enabled=False,
    )
    sub_loyal = SubscriptionState(
        subscription_id="sub_loyal_1",
        customer_id="cust_loyal",
        merchant_id="merch_1",
        plan_name="VIP Cloud",
        renewal_amount=10000.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        customer_history=hist_loyal,
        backup_method="UPI_AUTOPAY",
        last_failure_code="CARD_EXPIRED",
    )

    probs_loyal = predictor.predict_action_probabilities(sub_loyal, "CARD_EXPIRED")
    # Expired card cannot be immediately retried
    assert probs_loyal[SubscriptionAction.RETRY_PAYMENT.value] == 0.0
    # Switching to backup UPI AutoPay should have very high probability
    assert probs_loyal[SubscriptionAction.SWITCH_PAYMENT_METHOD.value] >= 0.82
    # Dunning link probability boosted by loyalty
    assert probs_loyal[SubscriptionAction.SEND_RECOVERY_MESSAGE.value] > 0.50

    # 2. First-time subscriber with no backup method and declined card
    hist_new = SubscriptionCustomerHistory(
        customer_id="cust_new",
        tenure_months=1,
        consecutive_successful_renewals=0,
        lifetime_billing_volume=2000.0,
        past_decline_count=2,
        primary_payment_method="CARD",
        backup_payment_method=None,
        risk_score=0.08,
        dnd_enabled=False,
    )
    sub_new = SubscriptionState(
        subscription_id="sub_new_1",
        customer_id="cust_new",
        merchant_id="merch_1",
        plan_name="Starter",
        renewal_amount=2000.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        customer_history=hist_new,
        backup_method=None,
        last_failure_code="CARD_DECLINED",
    )

    probs_new = predictor.predict_action_probabilities(sub_new, "CARD_DECLINED")
    # No backup method available -> SWITCH_PAYMENT_METHOD very low
    assert probs_new[SubscriptionAction.SWITCH_PAYMENT_METHOD.value] <= 0.10


def test_decision_engine_ranks_all_six_actions_and_enforces_policy():
    """Verifies Decision Engine evaluates all 6 actions, enforces retry limits, and respects DND/VIP policy."""
    engine = SubscriptionDecisionEngine()
    now = datetime.now(timezone.utc)

    # Case A: Card Expired with Backup Available -> SWITCH_PAYMENT_METHOD selected
    sub_switch = SubscriptionState(
        subscription_id="sub_dec_switch",
        customer_id="cust_s1",
        merchant_id="merch_1",
        plan_name="Pro Tier",
        renewal_amount=5000.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        last_failure_code="CARD_EXPIRED",
        backup_method="UPI_AUTOPAY",
    )
    dec_switch = engine.evaluate_candidates(sub_switch)
    assert dec_switch["selected_action"] == SubscriptionAction.SWITCH_PAYMENT_METHOD.value
    assert dec_switch["policy_outcome"] == "ALLOW"
    assert len(dec_switch["candidates"]) == 6

    # Case B: DND active -> SEND_RECOVERY_MESSAGE rejected by POL-009
    sub_dnd = SubscriptionState(
        subscription_id="sub_dec_dnd",
        customer_id="cust_dnd",
        merchant_id="merch_1",
        plan_name="Pro Tier",
        renewal_amount=5000.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        last_failure_code="INSUFFICIENT_FUNDS",
        backup_method=None,
        customer_history=SubscriptionCustomerHistory(customer_id="cust_dnd", dnd_enabled=True),
    )
    dec_dnd = engine.evaluate_candidates(sub_dnd)
    # Selected action must NOT be SEND_RECOVERY_MESSAGE
    assert dec_dnd["selected_action"] != SubscriptionAction.SEND_RECOVERY_MESSAGE.value
    msg_candidate = next(c for c in dec_dnd["candidates"] if c["action"] == SubscriptionAction.SEND_RECOVERY_MESSAGE.value)
    assert msg_candidate["permitted"] is False
    assert msg_candidate["rule_id"] == "POL-009"

    # Case C: Exceeded retry limits (attempts >= 3) -> RETRY_PAYMENT blocked by POL-004
    sub_limit = SubscriptionState(
        subscription_id="sub_dec_limit",
        customer_id="cust_lim",
        merchant_id="merch_1",
        plan_name="Pro Tier",
        renewal_amount=3000.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        current_attempt_count=3,
        last_failure_code="INSUFFICIENT_FUNDS",
    )
    dec_limit = engine.evaluate_candidates(sub_limit)
    retry_candidate = next(c for c in dec_limit["candidates"] if c["action"] == SubscriptionAction.RETRY_PAYMENT.value)
    assert retry_candidate["permitted"] is False
    assert retry_candidate["rule_id"] == "POL-004"


def test_subscription_simulator_actions():
    """Verifies simulator executes method switching, dunning conversion, and cancellation."""
    sim = SubscriptionSimulator(seed=42)
    now = datetime.now(timezone.utc)

    # 1. SWITCH_PAYMENT_METHOD execution
    sub_switch = SubscriptionState(
        subscription_id="sub_sim_switch",
        customer_id="cust_sw",
        merchant_id="merch_1",
        plan_name="Cloud Plus",
        renewal_amount=4500.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        primary_method="CARD",
        backup_method="UPI_AUTOPAY",
    )
    res_switch = sim.execute(sub_switch, SubscriptionAction.SWITCH_PAYMENT_METHOD.value, probability=1.0)
    assert res_switch["status"] == "SUCCESS"
    assert res_switch["recovered"] is True
    assert sub_switch.primary_method == "UPI_AUTOPAY"
    assert sub_switch.current_state == SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED
    assert sub_switch.recovered is True

    # 2. SCHEDULE_RETRY execution
    sub_sched = SubscriptionState(
        subscription_id="sub_sim_sched",
        customer_id="cust_sc",
        merchant_id="merch_1",
        plan_name="Cloud Plus",
        renewal_amount=4500.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
    )
    res_sched = sim.execute(sub_sched, SubscriptionAction.SCHEDULE_RETRY.value, probability=0.0)
    assert res_sched["status"] == "PENDING_RETRY"
    assert sub_sched.current_state == SubscriptionLifecycleState.RETRY_SCHEDULED

    # 3. STOP execution -> SUBSCRIPTION_CANCELLED
    sub_stop = SubscriptionState(
        subscription_id="sub_sim_stop",
        customer_id="cust_st",
        merchant_id="merch_1",
        plan_name="Cloud Plus",
        renewal_amount=4500.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
    )
    res_stop = sim.execute(sub_stop, SubscriptionAction.STOP.value, probability=0.0)
    assert res_stop["status"] == "CANCELLED"
    assert sub_stop.current_state == SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED
    assert sub_stop.recovered is False


def test_subscription_recovery_agent_audit_trail():
    """Verifies end-to-end pipeline execution logs immutable SHA-256 audit events."""
    agent = SubscriptionRecoveryAgent()
    now = datetime.now(timezone.utc)

    sub = SubscriptionState(
        subscription_id="sub_agent_test",
        customer_id="cust_ag",
        merchant_id="merch_1",
        plan_name="Enterprise Dev",
        renewal_amount=12000.0,
        current_state=SubscriptionLifecycleState.PAYMENT_FAILED,
        created_at=now,
        updated_at=now,
        last_failure_code="CARD_EXPIRED",
        backup_method="UPI_AUTOPAY",
    )

    result = agent.run_pipeline(sub, failure_code="CARD_EXPIRED")
    assert result["subscription_id"] == "sub_agent_test"
    assert result["selected_action"] == SubscriptionAction.SWITCH_PAYMENT_METHOD.value
    assert result["audit_hash"] is not None
    assert len(result["audit_hash"]) == 64
    assert sub.audit_hash == result["audit_hash"]


def test_subscription_api_endpoints(client):
    """Verifies all Phase 18 subscription REST API endpoints."""
    # 1. List subscriptions
    res = client.get("/api/subscriptions")
    assert res.status_code == 200
    data = res.json()
    assert "subscriptions" in data
    assert len(data["subscriptions"]) >= 5

    # 2. Get individual subscription
    first_id = data["subscriptions"][0]["subscription_id"]
    res_get = client.get(f"/api/subscriptions/{first_id}")
    assert res_get.status_code == 200
    sub_data = res_get.json()
    assert "subscription" in sub_data
    assert "customer_history" in sub_data
    assert "events" in sub_data

    # 3. Create new subscription
    create_payload = {
        "customer_id": "cust_api_sub_new",
        "plan_name": "Pro Annual Plan",
        "renewal_amount": 11999.0,
        "billing_cycle": "ANNUAL",
        "primary_method": "CARD",
        "backup_method": "UPI_AUTOPAY",
        "tenure_months": 12,
        "consecutive_successful_renewals": 1,
        "risk_score": 0.02,
        "dnd_enabled": False,
    }
    res_create = client.post("/api/subscriptions", json=create_payload)
    assert res_create.status_code == 200
    new_sub = res_create.json()
    new_id = new_sub["subscription_id"]
    assert new_sub["renewal_amount"] == 11999.0
    assert new_sub["current_state"] == "SUBSCRIPTION_CREATED"

    # 4. Record lifecycle event
    res_evt = client.post(
        f"/api/subscriptions/{new_id}/events",
        json={"state": "PAYMENT_FAILED", "metadata": {"failure_code": "INSUFFICIENT_FUNDS"}},
    )
    assert res_evt.status_code == 200
    assert res_evt.json()["current_state"] == "PAYMENT_FAILED"

    # 5. Run recovery pipeline
    res_recover = client.post(
        f"/api/subscriptions/{new_id}/recover",
        json={"failure_code": "INSUFFICIENT_FUNDS"},
    )
    assert res_recover.status_code == 200
    rec_res = res_recover.json()
    assert rec_res["subscription_id"] == new_id
    assert "selected_action" in rec_res
    assert "candidates" in rec_res
    assert "audit_hash" in rec_res
