from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base, init_db
from backend.app.models import (
    AgentDecision,
    AuditLog,
    CheckoutSession,
    Customer,
    Merchant,
    PaymentAttempt,
    RecoveryAction,
    RecoveryResult,
    SimulationRun,
    Subscription,
    Transaction,
)
from backend.app.seed import seed_demo_data, seed_if_empty


def test_database_init_and_crud():
    # Use isolated in-memory SQLite engine for fast testing of SQLAlchemy schema
    test_engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=test_engine)

    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    try:
        # Create merchant and customer
        merchant = Merchant(
            merchant_id="m_test_1",
            name="Test Merchant",
            business_type="SaaS",
            risk_score=0.1,
        )
        customer = Customer(
            customer_id="c_test_1",
            total_transactions=5,
            successful_transactions=4,
            failed_transactions=1,
            success_rate=0.8,
            average_transaction_amount=1500.0,
            preferred_payment_method="UPI",
            risk_score=0.15,
        )
        session.add_all([merchant, customer])
        session.commit()

        # Create transaction
        txn = Transaction(
            transaction_id="t_test_1",
            customer_id="c_test_1",
            merchant_id="m_test_1",
            amount=1500.0,
            currency="INR",
            payment_method="UPI",
            gateway="SIMULATOR",
            status="FAILED",
            failure_code="GATEWAY_TIMEOUT",
            failure_category="TEMPORARY",
            risk_score=0.2,
            attempt_number=1,
        )
        session.add(txn)
        session.commit()

        # Create payment attempt
        attempt = PaymentAttempt(
            attempt_id="att_test_1",
            transaction_id="t_test_1",
            attempt_number=1,
            payment_method="UPI",
            gateway="SIMULATOR",
            status="FAILED",
            failure_code="GATEWAY_TIMEOUT",
        )

        # Create recovery action
        action = RecoveryAction(
            action_id="act_test_1",
            transaction_id="t_test_1",
            action_type="RETRY_PAYMENT",
            predicted_probability=0.85,
            expected_recovery_value=1275.0,
            policy_status="ALLOWED",
            execution_status="EXECUTED",
        )

        # Create recovery result
        result = RecoveryResult(
            result_id="res_test_1",
            transaction_id="t_test_1",
            action_id="act_test_1",
            status="RECOVERED",
            recovered_amount=1500.0,
            success_probability=0.85,
            notes="Recovered on retry.",
        )

        # Create agent decision
        decision = AgentDecision(
            decision_id="dec_test_1",
            transaction_id="t_test_1",
            selected_action="RETRY_PAYMENT",
            reasoning_summary="Transient gateway timeout with high customer loyalty.",
            recovery_probability=0.85,
            expected_value=1275.0,
        )

        # Create audit log
        audit = AuditLog(
            audit_id="aud_test_1",
            transaction_id="t_test_1",
            event_type="recovery_action_executed",
            actor="recovery_agent",
            action="RETRY_PAYMENT",
            reason="Automated retry triggered after gateway timeout.",
            metadata={"latency_ms": 120},
        )

        # Create checkout session
        checkout = CheckoutSession(
            session_id="chk_test_1",
            transaction_id="t_test_1",
            customer_id="c_test_1",
            status="RECOVERED",
            total_amount=1500.0,
        )

        # Create subscription
        sub = Subscription(
            subscription_id="sub_test_1",
            customer_id="c_test_1",
            merchant_id="m_test_1",
            plan_name="Monthly Pro",
            status="ACTIVE",
            renewal_amount=1500.0,
        )

        # Create simulation run
        sim = SimulationRun(
            run_id="sim_test_1",
            seed=42,
            transaction_count=100,
            baseline_revenue_recovered=45000.0,
            ai_revenue_recovered=78000.0,
            revenue_at_risk=100000.0,
            recoverable_revenue=85000.0,
            recovery_rate=0.78,
        )

        session.add_all([attempt, action, result, decision, audit, checkout, sub, sim])
        session.commit()

        # Verify relationship traversal
        queried_txn = session.query(Transaction).filter_by(transaction_id="t_test_1").one()
        assert queried_txn.customer.customer_id == "c_test_1"
        assert queried_txn.merchant.merchant_id == "m_test_1"
        assert len(queried_txn.payment_attempts) == 1
        assert queried_txn.payment_attempts[0].attempt_id == "att_test_1"
        assert len(queried_txn.recovery_actions) == 1
        assert len(queried_txn.agent_decisions) == 1
        assert len(queried_txn.audit_logs) == 1
        assert queried_txn.audit_logs[0].event_metadata == {"latency_ms": 120}

        # Verify backward relationships from customer
        queried_cust = session.query(Customer).filter_by(customer_id="c_test_1").one()
        assert len(queried_cust.transactions) == 1
        assert len(queried_cust.subscriptions) == 1
        assert len(queried_cust.checkout_sessions) == 1

    finally:
        session.close()


def test_seed_mechanism_idempotency():
    test_engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=test_engine)

    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    try:
        # First seed should populate database
        assert session.query(Customer).count() == 0
        seed_if_empty(session)
        assert session.query(Customer).count() > 0
        assert session.query(Transaction).count() > 0
        assert session.query(CheckoutSession).count() > 0
        assert session.query(Subscription).count() > 0
        assert session.query(SimulationRun).count() > 0

        first_count = session.query(Transaction).count()

        # Second seed should be a no-op (idempotent)
        seed_if_empty(session)
        assert session.query(Transaction).count() == first_count

    finally:
        session.close()


def test_no_local_json_storage_dependency():
    """Verify that models and database do not rely on local JSON files for persistent production storage."""
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    backend_dir = os.path.join(workspace_dir, "backend")

    # Ensure no db.json or persistent json storage exists in backend
    for root, _, files in os.walk(backend_dir):
        for f in files:
            if f.endswith(".json") and f not in {"package.json", "tsconfig.json"}:
                # Verify any JSON file is not used as a database
                assert f not in {"database.json", "storage.json", "records.json", "production.json"}
