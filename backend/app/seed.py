from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

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



def seed_demo_data(db: Session) -> None:
    merchant = Merchant(
        merchant_id="merch_001",
        name="UrbanCart",
        business_type="E-commerce",
        risk_score=0.12,
    )
    customer = Customer(
        customer_id="cust_001",
        total_transactions=12,
        successful_transactions=10,
        failed_transactions=2,
        success_rate=0.83,
        average_transaction_amount=2450.0,
        preferred_payment_method="CARD",
        risk_score=0.21,
    )
    db.add_all([merchant, customer])
    db.flush()

    transaction = Transaction(
        transaction_id="txn_001",
        customer_id=customer.customer_id,
        merchant_id=merchant.merchant_id,
        amount=3200.0,
        currency="INR",
        payment_method="CARD",
        gateway="SIMULATOR",
        status="FAILED",
        failure_code="CARD_DECLINED",
        failure_category="PAYMENT_METHOD",
        risk_score=0.31,
        attempt_number=1,
    )
    db.add(transaction)
    db.flush()

    attempt = PaymentAttempt(
        attempt_id="att_001",
        transaction_id=transaction.transaction_id,
        attempt_number=1,
        payment_method="CARD",
        gateway="SIMULATOR",
        status="FAILED",
        failure_code="CARD_DECLINED",
    )
    action = RecoveryAction(
        action_id="ra_001",
        transaction_id=transaction.transaction_id,
        action_type="RETRY_PAYMENT",
        predicted_probability=0.74,
        expected_recovery_value=2250.0,
        policy_status="ALLOWED",
        execution_status="QUEUED",
    )
    decision = AgentDecision(
        decision_id="ad_001",
        transaction_id=transaction.transaction_id,
        selected_action="RETRY_PAYMENT",
        reasoning_summary="Temporary card decline with medium customer risk and high retry potential.",
        recovery_probability=0.74,
        expected_value=2250.0,
    )
    result = RecoveryResult(
        result_id="rr_001",
        transaction_id=transaction.transaction_id,
        action_id=action.action_id,
        status="PENDING",
        recovered_amount=0.0,
        success_probability=0.74,
        notes="Demo result placeholder.",
    )
    audit = AuditLog(
        audit_id="audit_001",
        transaction_id=transaction.transaction_id,
        event_type="payment_failure",
        actor="system",
        action="ingest",
        reason="Synthetic demo event generated for database validation.",
        metadata={"source": "seed", "model": "demo"},
    )
    session = CheckoutSession(
        session_id="cs_001",
        transaction_id=transaction.transaction_id,
        customer_id=customer.customer_id,
        status="ABANDONED",
        abandonment_reason="PAYMENT_FAILED",
        total_amount=3200.0,
    )
    subscription = Subscription(
        subscription_id="sub_001",
        customer_id=customer.customer_id,
        merchant_id=merchant.merchant_id,
        plan_name="Premium Pro Annual",
        status="ACTIVE",
        renewal_amount=4999.0,
    )
    run = SimulationRun(
        run_id="run_001",
        seed=42,
        transaction_count=1,
        baseline_revenue_recovered=1200.0,
        ai_revenue_recovered=2200.0,
        revenue_at_risk=3200.0,
        recoverable_revenue=2500.0,
        recovery_rate=0.69,
    )
    db.add_all([session, subscription, attempt, action, decision, result, audit, run])
    db.commit()


def seed_if_empty(db: Session) -> None:
    if db.query(Customer).count() == 0 and db.query(Transaction).count() == 0:
        seed_demo_data(db)


if __name__ == "__main__":
    from backend.app.database import SessionLocal, init_db

    init_db()
    with SessionLocal() as db_session:
        seed_if_empty(db_session)
    print("Database seeding completed successfully.")

