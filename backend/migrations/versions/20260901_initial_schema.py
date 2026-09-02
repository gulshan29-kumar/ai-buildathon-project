"""Initial schema

Revision ID: 20260901_initial_schema
Revises: 
Create Date: 2026-09-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260901_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("total_transactions", sa.Integer(), nullable=False),
        sa.Column("successful_transactions", sa.Integer(), nullable=False),
        sa.Column("failed_transactions", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("average_transaction_amount", sa.Float(), nullable=False),
        sa.Column("preferred_payment_method", sa.String(length=32), nullable=False),
        sa.Column("customer_since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("customer_id"),
    )
    op.create_index(op.f("ix_customers_risk_score"), "customers", ["risk_score"], unique=False)
    op.create_index(op.f("ix_customers_success_rate"), "customers", ["success_rate"], unique=False)

    op.create_table(
        "merchants",
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("business_type", sa.String(length=64), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("merchant_id"),
    )

    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("gateway", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.merchant_id"]),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_index(op.f("ix_transactions_customer_id"), "transactions", ["customer_id"], unique=False)
    op.create_index(op.f("ix_transactions_merchant_id"), "transactions", ["merchant_id"], unique=False)
    op.create_index(op.f("ix_transactions_status"), "transactions", ["status"], unique=False)
    op.create_index(op.f("ix_transactions_failure_code"), "transactions", ["failure_code"], unique=False)
    op.create_index(op.f("ix_transactions_risk_score"), "transactions", ["risk_score"], unique=False)
    op.create_index(op.f("ix_transactions_created_at"), "transactions", ["created_at"], unique=False)

    op.create_table(
        "payment_attempts",
        sa.Column("attempt_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("gateway", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint("transaction_id", "attempt_number", name="uq_payment_attempt_transaction_attempt"),
    )
    op.create_index(op.f("ix_payment_attempts_transaction_id"), "payment_attempts", ["transaction_id"], unique=False)
    op.create_index(op.f("ix_payment_attempts_status"), "payment_attempts", ["status"], unique=False)

    op.create_table(
        "checkout_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=True),
        sa.Column("customer_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("abandonment_reason", sa.String(length=128), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_checkout_sessions_status"), "checkout_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_checkout_sessions_customer_id"), "checkout_sessions", ["customer_id"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("subscription_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("plan_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("renewal_amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.merchant_id"]),
        sa.PrimaryKeyConstraint("subscription_id"),
    )
    op.create_index(op.f("ix_subscriptions_customer_id"), "subscriptions", ["customer_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_status"), "subscriptions", ["status"], unique=False)

    op.create_table(
        "recovery_actions",
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("predicted_probability", sa.Float(), nullable=False),
        sa.Column("expected_recovery_value", sa.Float(), nullable=False),
        sa.Column("policy_status", sa.String(length=32), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index(op.f("ix_recovery_actions_transaction_id"), "recovery_actions", ["transaction_id"], unique=False)
    op.create_index(op.f("ix_recovery_actions_action_type"), "recovery_actions", ["action_type"], unique=False)

    op.create_table(
        "recovery_results",
        sa.Column("result_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recovered_amount", sa.Float(), nullable=False),
        sa.Column("success_probability", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.ForeignKeyConstraint(["action_id"], ["recovery_actions.action_id"]),
        sa.PrimaryKeyConstraint("result_id"),
    )
    op.create_index(op.f("ix_recovery_results_transaction_id"), "recovery_results", ["transaction_id"], unique=False)
    op.create_index(op.f("ix_recovery_results_status"), "recovery_results", ["status"], unique=False)

    op.create_table(
        "agent_decisions",
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("selected_action", sa.String(length=64), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("recovery_probability", sa.Float(), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index(op.f("ix_agent_decisions_transaction_id"), "agent_decisions", ["transaction_id"], unique=False)
    op.create_index(op.f("ix_agent_decisions_selected_action"), "agent_decisions", ["selected_action"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(op.f("ix_audit_logs_transaction_id"), "audit_logs", ["transaction_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_event_type"), "audit_logs", ["event_type"], unique=False)

    op.create_table(
        "simulation_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("baseline_revenue_recovered", sa.Float(), nullable=False),
        sa.Column("ai_revenue_recovered", sa.Float(), nullable=False),
        sa.Column("revenue_at_risk", sa.Float(), nullable=False),
        sa.Column("recoverable_revenue", sa.Float(), nullable=False),
        sa.Column("recovery_rate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(op.f("ix_simulation_runs_seed"), "simulation_runs", ["seed"], unique=False)
    op.create_index(op.f("ix_simulation_runs_created_at"), "simulation_runs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_simulation_runs_created_at"), table_name="simulation_runs")
    op.drop_index(op.f("ix_simulation_runs_seed"), table_name="simulation_runs")
    op.drop_table("simulation_runs")
    op.drop_index(op.f("ix_audit_logs_event_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_transaction_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_agent_decisions_selected_action"), table_name="agent_decisions")
    op.drop_index(op.f("ix_agent_decisions_transaction_id"), table_name="agent_decisions")
    op.drop_table("agent_decisions")
    op.drop_index(op.f("ix_recovery_results_status"), table_name="recovery_results")
    op.drop_index(op.f("ix_recovery_results_transaction_id"), table_name="recovery_results")
    op.drop_table("recovery_results")
    op.drop_index(op.f("ix_recovery_actions_action_type"), table_name="recovery_actions")
    op.drop_index(op.f("ix_recovery_actions_transaction_id"), table_name="recovery_actions")
    op.drop_table("recovery_actions")
    op.drop_index(op.f("ix_subscriptions_status"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_customer_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index(op.f("ix_checkout_sessions_customer_id"), table_name="checkout_sessions")
    op.drop_index(op.f("ix_checkout_sessions_status"), table_name="checkout_sessions")
    op.drop_table("checkout_sessions")
    op.drop_index(op.f("ix_payment_attempts_status"), table_name="payment_attempts")
    op.drop_index(op.f("ix_payment_attempts_transaction_id"), table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_index(op.f("ix_transactions_created_at"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_risk_score"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_failure_code"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_status"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_merchant_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_customer_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("merchants")
    op.drop_index(op.f("ix_customers_success_rate"), table_name="customers")
    op.drop_index(op.f("ix_customers_risk_score"), table_name="customers")
    op.drop_table("customers")
