from __future__ import annotations

import pytest

from backend.app.simulator import (
    InvalidStateTransitionError,
    PaymentState,
    PolicyBlockedExecutionError,
    StatefulPaymentSimulator,
)


@pytest.fixture
def simulator():
    return StatefulPaymentSimulator(seed=42)


def test_all_eight_states_present():
    expected_states = {
        "CREATED",
        "INITIATED",
        "PROCESSING",
        "SUCCESS",
        "FAILED",
        "PENDING",
        "CANCELLED",
        "REFUNDED",
    }
    actual_states = {s.value for s in PaymentState}
    assert actual_states == expected_states


def test_state_transition_validation(simulator):
    # Valid flow
    payment = simulator.create_payment(amount=1000.0, failure_code="GATEWAY_TIMEOUT")
    assert payment["status"] == PaymentState.FAILED.value

    # Direct illegal transition: FAILED to REFUNDED is invalid
    with pytest.raises(InvalidStateTransitionError, match="Invalid state transition"):
        simulator._transition(payment, PaymentState.REFUNDED)


def test_seed_determinism():
    sim1 = StatefulPaymentSimulator(seed=999)
    sim2 = StatefulPaymentSimulator(seed=999)

    res1 = [sim1.create_payment(amount=1000.0)["status"] for _ in range(10)]
    res2 = [sim2.create_payment(amount=1000.0)["status"] for _ in range(10)]
    assert res1 == res2


def test_temporary_gateway_failure_retry_succeeds(simulator):
    payment = simulator.create_payment(amount=2000.0, failure_code="GATEWAY_TIMEOUT")
    assert payment["status"] == "FAILED"

    # Retry on gateway timeout
    retry_res = simulator.retry_payment(payment["transaction_id"])
    assert retry_res["status"] == "SUCCESS"
    assert retry_res["attempt_number"] == 2
    assert retry_res["simulated"] is True


def test_expired_card_same_card_retry_fails(simulator):
    payment = simulator.create_payment(amount=1500.0, failure_code="CARD_EXPIRED")
    assert payment["status"] == "FAILED"

    # Policy denies retry on expired card, raising policy blocked execution
    with pytest.raises(PolicyBlockedExecutionError, match="Execution blocked by policy"):
        simulator.retry_payment(payment["transaction_id"])


def test_insufficient_funds_immediate_retry_fails_delayed_succeeds():
    sim = StatefulPaymentSimulator(seed=42)
    payment = sim.create_payment(amount=3000.0, failure_code="INSUFFICIENT_FUNDS")
    assert payment["status"] == "FAILED"

    # Immediate retry (delay=0) should fail
    retry_res = sim.retry_payment(payment["transaction_id"], delay_seconds=0)
    assert retry_res["status"] == "FAILED"

    # With cooldown delay (300s), retry can succeed
    delayed_retry = sim.retry_payment(payment["transaction_id"], delay_seconds=300)
    assert delayed_retry["status"] == "SUCCESS"


def test_switch_payment_method_succeeds(simulator):
    payment = simulator.create_payment(
        amount=2500.0,
        payment_method="CARD",
        failure_code="CARD_EXPIRED",
    )
    assert payment["status"] == "FAILED"

    # Switch to UPI
    switch_res = simulator.switch_payment_method(payment["transaction_id"], "UPI")
    assert switch_res["status"] == "SUCCESS"
    assert switch_res["payment_method"] == "UPI"
    assert switch_res["simulated"] is True


def test_high_risk_blocked_before_execution(simulator):
    # High-risk payment must never reach execution
    with pytest.raises(PolicyBlockedExecutionError, match="Execution blocked by policy"):
        simulator.create_payment(amount=50000.0, risk_score=0.98, failure_code="HIGH_RISK")


def test_duplicate_payment_prevented(simulator):
    idempotency_key = "idem_unique_key_123"
    p1 = simulator.create_payment(amount=1000.0, idempotency_key=idempotency_key)
    assert p1["simulated"] is True

    # Attempt second payment with identical key
    p2 = simulator.create_payment(amount=1000.0, idempotency_key=idempotency_key)
    assert p2["error"] == "DUPLICATE_PAYMENT_PREVENTED"
    assert p2["transaction_id"] == p1["transaction_id"]


def test_abandoned_checkout_message_causes_customer_return(simulator):
    payment = simulator.create_payment(amount=4500.0, failure_code="CUSTOMER_ABANDONED")
    assert payment["status"] == "FAILED"

    msg_res = simulator.send_recovery_message(payment["transaction_id"], channel="WHATSAPP")
    assert msg_res["message_sent"] is True
    assert msg_res["simulated"] is True
    assert msg_res["customer_returned"] is True
    assert msg_res["current_status"] == "SUCCESS"


def test_order_creation_failure_payment_succeeds_order_unresolved(simulator):
    payment = simulator.create_payment(amount=1200.0, failure_code="ORDER_CREATION_FAILED")
    # Payment itself captured at gateway, merchant order remains unresolved
    assert payment["status"] == "SUCCESS"
    assert payment["merchant_order_status"] == "UNRESOLVED"
    assert payment["failure_code"] == "ORDER_CREATION_FAILED"
    assert payment["simulated"] is True


def test_schedule_retry_and_get_status(simulator):
    payment = simulator.create_payment(amount=1800.0, failure_code="GATEWAY_TIMEOUT")
    job = simulator.schedule_retry(payment["transaction_id"], delay_seconds=120)
    assert job["status"] == "SCHEDULED"
    assert job["delay_seconds"] == 120
    assert job["simulated"] is True

    status = simulator.get_payment_status(payment["transaction_id"])
    assert status["status"] == "FAILED"
    assert status["events_count"] > 0
    assert status["simulated"] is True
    assert all(e["simulated"] is True for e in status["events"])


def test_refund_and_cancel_lifecycle(simulator):
    # Test SUCCESS -> REFUNDED
    p_success = simulator.create_payment(amount=5000.0, failure_code=None)
    # Ensure payment is SUCCESS (re-attempt if random roll wasn't success)
    if p_success["status"] != "SUCCESS":
        p_success = simulator.switch_payment_method(p_success["transaction_id"], "NETBANKING")

    refunded = simulator.refund_payment(p_success["transaction_id"], reason="Customer dispute")
    assert refunded["status"] == "REFUNDED"
    assert refunded["simulated"] is True

    # Attempting to transition from terminal REFUNDED state must fail
    with pytest.raises(InvalidStateTransitionError, match="Invalid state transition"):
        simulator._transition(refunded, PaymentState.PROCESSING)

    # Test FAILED -> CANCELLED
    p_fail = simulator.create_payment(amount=2000.0, failure_code="GATEWAY_TIMEOUT")
    assert p_fail["status"] == "FAILED"
    cancelled = simulator.cancel_payment(p_fail["transaction_id"], reason="Customer gave up")
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["simulated"] is True

    # Terminal CANCELLED state cannot transition
    with pytest.raises(InvalidStateTransitionError, match="Invalid state transition"):
        simulator._transition(cancelled, PaymentState.INITIATED)


def test_all_actions_create_audited_events_with_simulated_tag(simulator):
    payment = simulator.create_payment(amount=3200.0, failure_code="GATEWAY_TIMEOUT")
    txn_id = payment["transaction_id"]

    # Action 1: Retry
    simulator.retry_payment(txn_id)

    # Action 2: Schedule Retry
    simulator.schedule_retry(txn_id, delay_seconds=60)

    # Action 3: Message
    simulator.send_recovery_message(txn_id, channel="SMS")

    # Fetch status and events
    status = simulator.get_payment_status(txn_id)
    events = status["events"]

    assert len(events) >= 5
    for evt in events:
        assert evt["simulated"] is True
        assert evt["environment"] == "SIMULATED_GATEWAY_SANDBOX"
        assert evt["transaction_id"] == txn_id
        assert evt["timestamp"] is not None
        assert evt["event_id"].startswith("evt_")

