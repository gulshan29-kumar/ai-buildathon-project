from __future__ import annotations

from backend.app.database import Base
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


def test_all_eleven_models_registered():
    models = [
        Customer,
        Merchant,
        Transaction,
        PaymentAttempt,
        CheckoutSession,
        Subscription,
        RecoveryAction,
        RecoveryResult,
        AgentDecision,
        AuditLog,
        SimulationRun,
    ]
    assert len(models) == 11
    for m in models:
        assert issubclass(m, Base)
        assert hasattr(m, "__tablename__")


def test_table_names():
    assert Customer.__tablename__ == "customers"
    assert Merchant.__tablename__ == "merchants"
    assert Transaction.__tablename__ == "transactions"
    assert PaymentAttempt.__tablename__ == "payment_attempts"
    assert CheckoutSession.__tablename__ == "checkout_sessions"
    assert Subscription.__tablename__ == "subscriptions"
    assert RecoveryAction.__tablename__ == "recovery_actions"
    assert RecoveryResult.__tablename__ == "recovery_results"
    assert AgentDecision.__tablename__ == "agent_decisions"
    assert AuditLog.__tablename__ == "audit_logs"
    assert SimulationRun.__tablename__ == "simulation_runs"


def test_transaction_required_fields():
    expected_fields = {
        "transaction_id",
        "customer_id",
        "merchant_id",
        "amount",
        "currency",
        "payment_method",
        "gateway",
        "status",
        "failure_code",
        "failure_category",
        "risk_score",
        "attempt_number",
        "created_at",
        "updated_at",
    }
    actual_columns = {c.name for c in Transaction.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_customer_required_fields():
    expected_fields = {
        "customer_id",
        "total_transactions",
        "successful_transactions",
        "failed_transactions",
        "success_rate",
        "average_transaction_amount",
        "preferred_payment_method",
        "customer_since",
        "risk_score",
    }
    actual_columns = {c.name for c in Customer.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_payment_attempt_required_fields():
    expected_fields = {
        "attempt_id",
        "transaction_id",
        "attempt_number",
        "payment_method",
        "gateway",
        "status",
        "failure_code",
        "timestamp",
    }
    actual_columns = {c.name for c in PaymentAttempt.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_recovery_action_required_fields():
    expected_fields = {
        "action_id",
        "transaction_id",
        "action_type",
        "predicted_probability",
        "expected_recovery_value",
        "policy_status",
        "execution_status",
        "created_at",
    }
    actual_columns = {c.name for c in RecoveryAction.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_agent_decision_required_fields():
    expected_fields = {
        "decision_id",
        "transaction_id",
        "selected_action",
        "reasoning_summary",
        "recovery_probability",
        "expected_value",
        "created_at",
    }
    actual_columns = {c.name for c in AgentDecision.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_audit_log_required_fields():
    expected_fields = {
        "audit_id",
        "transaction_id",
        "event_type",
        "actor",
        "action",
        "reason",
        "metadata",
        "timestamp",
    }
    actual_columns = {c.name for c in AuditLog.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_simulation_run_required_fields():
    expected_fields = {
        "run_id",
        "seed",
        "transaction_count",
        "baseline_revenue_recovered",
        "ai_revenue_recovered",
        "revenue_at_risk",
        "recoverable_revenue",
        "recovery_rate",
        "created_at",
    }
    actual_columns = {c.name for c in SimulationRun.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_merchant_required_fields():
    expected_fields = {
        "merchant_id",
        "name",
        "business_type",
        "risk_score",
        "created_at",
        "updated_at",
    }
    actual_columns = {c.name for c in Merchant.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_checkout_session_required_fields():
    expected_fields = {
        "session_id",
        "transaction_id",
        "customer_id",
        "status",
        "abandonment_reason",
        "total_amount",
        "created_at",
        "updated_at",
    }
    actual_columns = {c.name for c in CheckoutSession.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_subscription_required_fields():
    expected_fields = {
        "subscription_id",
        "customer_id",
        "merchant_id",
        "plan_name",
        "status",
        "renewal_amount",
        "created_at",
        "updated_at",
    }
    actual_columns = {c.name for c in Subscription.__table__.columns}
    assert expected_fields.issubset(actual_columns)


def test_indexes_and_unique_constraints():
    # Verify PaymentAttempt unique constraint on (transaction_id, attempt_number)
    unique_constraints = [
        c for c in PaymentAttempt.__table__.constraints if hasattr(c, "columns")
    ]
    uc_col_sets = [{col.name for col in uc.columns} for uc in unique_constraints]
    assert {"transaction_id", "attempt_number"} in uc_col_sets

    # Verify transaction indexes
    txn_indexes = {idx.name for idx in Transaction.__table__.indexes}
    assert "ix_transactions_customer_id" in txn_indexes
    assert "ix_transactions_status" in txn_indexes
    assert "ix_transactions_risk_score" in txn_indexes
