import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.app.abandonment_recovery import (
    AbandonmentAction,
    AbandonmentDetector,
    AbandonmentFeatureExtractor,
    AbandonmentRecoveryPredictor,
    CheckoutDecisionEngine,
    CheckoutEvent,
    CheckoutLifecycleStage,
    CheckoutRecoveryAgent,
    CheckoutSessionState,
    CheckoutSessionStore,
    CheckoutSimulator,
)
from backend.app.main import app
from backend.app.policy_engine import PolicyEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_checkout_lifecycle_stages():
    """Verifies all 6 required lifecycle stages exist and can be traversed."""
    stages = [
        CheckoutLifecycleStage.PRODUCT_VIEW,
        CheckoutLifecycleStage.CHECKOUT_STARTED,
        CheckoutLifecycleStage.PAYMENT_PAGE_OPENED,
        CheckoutLifecycleStage.PAYMENT_INITIATED,
        CheckoutLifecycleStage.PAYMENT_SUCCESS,
        CheckoutLifecycleStage.ABANDONED,
    ]
    assert len(stages) == 6

    now = datetime.now(timezone.utc)
    sess = CheckoutSessionState(
        session_id="chk_test_stage",
        customer_id="cust_1",
        cart_value=5000.0,
        current_stage=CheckoutLifecycleStage.PRODUCT_VIEW,
        created_at=now,
        updated_at=now,
    )
    assert sess.current_stage == CheckoutLifecycleStage.PRODUCT_VIEW

    # Transition to checkout started
    sess.current_stage = CheckoutLifecycleStage.CHECKOUT_STARTED
    assert sess.current_stage == CheckoutLifecycleStage.CHECKOUT_STARTED

    # Transition to payment page opened
    sess.current_stage = CheckoutLifecycleStage.PAYMENT_PAGE_OPENED
    assert sess.current_stage == CheckoutLifecycleStage.PAYMENT_PAGE_OPENED

    # Transition to payment initiated
    sess.current_stage = CheckoutLifecycleStage.PAYMENT_INITIATED
    assert sess.current_stage == CheckoutLifecycleStage.PAYMENT_INITIATED

    # Terminal success
    sess.current_stage = CheckoutLifecycleStage.PAYMENT_SUCCESS
    assert sess.current_stage == CheckoutLifecycleStage.PAYMENT_SUCCESS


def test_abandonment_detection_timeout():
    """Verifies that an inactive session exceeding stage threshold is detected as abandoned."""
    old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    sess = CheckoutSessionState(
        session_id="chk_timeout_test",
        customer_id="cust_2",
        cart_value=8500.0,
        current_stage=CheckoutLifecycleStage.CHECKOUT_STARTED,  # Timeout threshold is 15 mins
        created_at=old_time,
        updated_at=old_time,
    )

    is_abandoned, reason = AbandonmentDetector.detect(sess)
    assert is_abandoned is True
    assert "INACTIVITY_TIMEOUT" in reason

    # Mark abandoned
    AbandonmentDetector.mark_abandoned(sess, reason)
    assert sess.current_stage == CheckoutLifecycleStage.ABANDONED
    assert sess.abandonment_detected is True
    assert sess.dropoff_stage == CheckoutLifecycleStage.CHECKOUT_STARTED


def test_abandonment_detection_explicit_dropoff():
    """Verifies explicit user drop-off triggers (e.g. window closed) detect abandonment immediately."""
    now = datetime.now(timezone.utc)
    sess = CheckoutSessionState(
        session_id="chk_explicit_test",
        customer_id="cust_3",
        cart_value=12000.0,
        current_stage=CheckoutLifecycleStage.PAYMENT_PAGE_OPENED,
        created_at=now,
        updated_at=now,
        events=[
            CheckoutEvent(
                event_id="evt_1",
                stage=CheckoutLifecycleStage.PAYMENT_PAGE_OPENED,
                timestamp=now,
                metadata={"trigger": "WINDOW_CLOSED"},
            )
        ],
    )

    is_abandoned, reason = AbandonmentDetector.detect(sess)
    assert is_abandoned is True
    assert "EXPLICIT_DROPOFF_WINDOW_CLOSED" in reason


def test_feature_extraction_all_eight_fields():
    """Verifies all 8 required features are properly extracted from the session state."""
    now = datetime.now(timezone.utc)
    sess = CheckoutSessionState(
        session_id="chk_feat_test",
        customer_id="cust_4",
        cart_value=15400.0,
        current_stage=CheckoutLifecycleStage.ABANDONED,
        created_at=now,
        updated_at=now,
        checkout_duration=145.0,
        device="MOBILE",
        payment_method="UPI",
        previous_purchases=5,
        previous_abandonment_count=2,
        risk_score=0.04,
        dnd_enabled=False,
    )

    features = AbandonmentFeatureExtractor.extract(sess)

    # Verify all 8 fields are present
    assert "cart_value" in features
    assert features["cart_value"] == 15400.0

    assert "checkout_duration" in features
    assert features["checkout_duration"] == 145.0

    assert "customer_history" in features
    assert features["customer_history"]["customer_id"] == "cust_4"
    assert features["customer_history"]["risk_score"] == 0.04

    assert "previous_purchases" in features
    assert features["previous_purchases"] == 5

    assert "payment_method" in features
    assert features["payment_method"] == "UPI"

    assert "device" in features
    assert features["device"] == "MOBILE"

    assert "time" in features
    assert "hour_of_day" in features["time"]
    assert "day_of_week" in features["time"]

    assert "previous_abandonment_count" in features
    assert features["previous_abandonment_count"] == 2


def test_abandonment_recovery_predictor():
    """Verifies recovery probabilities for SEND_RECOVERY_MESSAGE, SCHEDULE_RETRY, and STOP."""
    # 1. Standard low-risk mobile customer
    features_standard = {
        "cart_value": 7500.0,
        "checkout_duration": 90.0,
        "customer_history": {"risk_score": 0.03, "dnd_enabled": False},
        "previous_purchases": 3,
        "previous_abandonment_count": 0,
        "payment_method": "UPI",
        "device": "MOBILE",
        "time": {"hour_of_day": 14, "day_of_week": 2},
    }
    probs = AbandonmentRecoveryPredictor.predict_action_probabilities(features_standard)
    assert AbandonmentAction.SEND_RECOVERY_MESSAGE.value in probs
    assert AbandonmentAction.SCHEDULE_RETRY.value in probs
    assert AbandonmentAction.STOP.value in probs
    # High response expected on WhatsApp message for loyal low-risk customer
    assert probs[AbandonmentAction.SEND_RECOVERY_MESSAGE.value] > 0.70
    assert probs[AbandonmentAction.STOP.value] < 0.15

    # 2. High-risk fraud customer
    features_fraud = {
        "cart_value": 75000.0,
        "checkout_duration": 15.0,
        "customer_history": {"risk_score": 0.85, "dnd_enabled": False},
        "previous_purchases": 0,
        "previous_abandonment_count": 6,
        "payment_method": "CARD",
        "device": "DESKTOP",
        "time": {"hour_of_day": 3, "day_of_week": 1},
    }
    probs_fraud = AbandonmentRecoveryPredictor.predict_action_probabilities(features_fraud)
    # Active recovery should be suppressed
    assert probs_fraud[AbandonmentAction.SEND_RECOVERY_MESSAGE.value] == 0.0
    assert probs_fraud[AbandonmentAction.STOP.value] >= 0.90


def test_decision_engine_and_policy_guardrails():
    """Verifies Decision Engine ranks by EV and respects PolicyEngine rules including DND and Fraud."""
    engine = CheckoutDecisionEngine()
    now = datetime.now(timezone.utc)

    # Case A: Normal customer -> SEND_RECOVERY_MESSAGE selected
    sess_normal = CheckoutSessionState(
        session_id="chk_dec_1",
        customer_id="cust_norm",
        cart_value=10000.0,
        current_stage=CheckoutLifecycleStage.ABANDONED,
        created_at=now,
        updated_at=now,
        previous_purchases=4,
        previous_abandonment_count=1,
        risk_score=0.03,
        dnd_enabled=False,
    )
    features_normal = AbandonmentFeatureExtractor.extract(sess_normal)
    dec_normal = engine.evaluate_candidates(sess_normal, features_normal)
    assert dec_normal["selected_action"] == AbandonmentAction.SEND_RECOVERY_MESSAGE.value
    assert dec_normal["policy_outcome"] == "ALLOW"
    assert dec_normal["expected_recovery_value"] > 5000.0

    # Case B: DND customer -> SEND_RECOVERY_MESSAGE blocked by POL-009, falls back to SCHEDULE_RETRY or STOP
    sess_dnd = CheckoutSessionState(
        session_id="chk_dec_dnd",
        customer_id="cust_dnd",
        cart_value=10000.0,
        current_stage=CheckoutLifecycleStage.ABANDONED,
        created_at=now,
        updated_at=now,
        previous_purchases=2,
        previous_abandonment_count=1,
        risk_score=0.04,
        dnd_enabled=True,
    )
    features_dnd = AbandonmentFeatureExtractor.extract(sess_dnd)
    dec_dnd = engine.evaluate_candidates(sess_dnd, features_dnd)
    # Message must NOT be selected when DND is enabled
    assert dec_dnd["selected_action"] != AbandonmentAction.SEND_RECOVERY_MESSAGE.value
    # Candidate message action should show rejection by POL-009
    msg_candidate = next(c for c in dec_dnd["candidates"] if c["action"] == AbandonmentAction.SEND_RECOVERY_MESSAGE.value)
    assert msg_candidate["permitted"] is False
    assert msg_candidate["rule_id"] == "POL-009"


def test_simulator_execution_and_conversion():
    """Verifies simulator execution converts customer on message and marks PAYMENT_SUCCESS."""
    sim = CheckoutSimulator(seed=42)
    now = datetime.now(timezone.utc)

    sess = CheckoutSessionState(
        session_id="chk_sim_conv",
        customer_id="cust_conv",
        cart_value=12500.0,
        current_stage=CheckoutLifecycleStage.ABANDONED,
        created_at=now,
        updated_at=now,
    )

    # Execute recovery message with high probability
    result = sim.execute(sess, AbandonmentAction.SEND_RECOVERY_MESSAGE.value, probability=1.0)
    assert result["status"] == "SUCCESS"
    assert result["customer_converted"] is True
    assert sess.current_stage == CheckoutLifecycleStage.PAYMENT_SUCCESS
    assert sess.recovered is True
    assert sess.recovered_amount == 12500.0

    # Test STOP action halts without recovery
    sess_stop = CheckoutSessionState(
        session_id="chk_sim_stop",
        customer_id="cust_stop",
        cart_value=20000.0,
        current_stage=CheckoutLifecycleStage.ABANDONED,
        created_at=now,
        updated_at=now,
    )
    res_stop = sim.execute(sess_stop, AbandonmentAction.STOP.value, probability=0.0)
    assert res_stop["status"] == "STOPPED"
    assert sess_stop.recovered is False
    assert sess_stop.recovered_amount == 0.0


def test_checkout_recovery_agent_audit_trail():
    """Verifies end-to-end agent pipeline execution with SHA-256 cryptographic audit chaining."""
    agent = CheckoutRecoveryAgent()
    now = datetime.now(timezone.utc)

    sess = CheckoutSessionState(
        session_id="chk_agent_test",
        customer_id="cust_agent",
        cart_value=8900.0,
        current_stage=CheckoutLifecycleStage.CHECKOUT_STARTED,
        created_at=now - timedelta(minutes=25),
        updated_at=now - timedelta(minutes=25),
        previous_purchases=3,
        device="MOBILE",
    )

    pipeline_result = agent.run_pipeline(sess)
    assert pipeline_result["session_id"] == "chk_agent_test"
    assert pipeline_result["selected_action"] in [
        AbandonmentAction.SEND_RECOVERY_MESSAGE.value,
        AbandonmentAction.SCHEDULE_RETRY.value,
    ]
    assert pipeline_result["audit_hash"] is not None
    assert len(pipeline_result["audit_hash"]) == 64  # Valid SHA-256 hex string
    assert sess.audit_hash == pipeline_result["audit_hash"]


def test_api_endpoints_and_dashboard_metrics(client):
    """Verifies all Phase 17 checkout API endpoints and dashboard metrics calculation."""
    # 1. List checkout sessions
    res = client.get("/api/checkout/sessions")
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data
    assert "metrics" in data
    assert len(data["sessions"]) >= 5

    # 2. Create new checkout session
    create_payload = {
        "customer_id": "cust_api_new",
        "cart_value": 14200.0,
        "stage": "PRODUCT_VIEW",
        "device": "MOBILE",
        "payment_method": "UPI",
        "previous_purchases": 3,
        "previous_abandonment_count": 0,
        "risk_score": 0.04,
        "dnd_enabled": False,
    }
    res_create = client.post("/api/checkout/sessions", json=create_payload)
    assert res_create.status_code == 200
    new_sess = res_create.json()
    session_id = new_sess["session_id"]
    assert new_sess["cart_value"] == 14200.0
    assert new_sess["current_stage"] == "PRODUCT_VIEW"

    # 3. Record lifecycle progression event
    res_evt = client.post(
        f"/api/checkout/sessions/{session_id}/events",
        json={"stage": "CHECKOUT_STARTED", "metadata": {"button": "proceed_to_checkout"}},
    )
    assert res_evt.status_code == 200
    assert res_evt.json()["current_stage"] == "CHECKOUT_STARTED"

    # 4. Detect abandonments
    res_detect = client.post("/api/checkout/detect")
    assert res_detect.status_code == 200
    assert "detected_count" in res_detect.json()

    # 5. Run recovery on abandoned session
    res_recover = client.post(
        f"/api/checkout/recover/{session_id}",
        json={"force_action": "SEND_RECOVERY_MESSAGE"},
    )
    assert res_recover.status_code == 200
    rec_data = res_recover.json()
    assert rec_data["session_id"] == session_id
    assert rec_data["selected_action"] == "SEND_RECOVERY_MESSAGE"
    assert "audit_hash" in rec_data
    assert "candidates" in rec_data

    # 6. Verify Dashboard Metrics include Phase 17 fields
    res_metrics = client.get("/api/dashboard/metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert "abandoned_checkout_revenue" in metrics
    assert "recoverable_abandonment_revenue" in metrics
    assert "recovered_abandonment_revenue" in metrics
    assert metrics["abandoned_checkout_revenue"] > 0
    assert metrics["recoverable_abandonment_revenue"] > 0
