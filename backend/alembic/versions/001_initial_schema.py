"""Initial schema — all 13 tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
import sqlmodel

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ── user_profiles ──────────────────────────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("age_range", sa.String(10), nullable=False),
        sa.Column("occupation", sa.String(50), nullable=False),
        sa.Column("income_source", sa.String(50), nullable=False),
        sa.Column("monthly_income_range", sa.String(30), nullable=False),
        sa.Column("credit_limit", sa.Numeric(10, 2), nullable=False),
        sa.Column("billing_cycle_day", sa.Integer(), nullable=True),
        sa.Column("billing_cycle_set", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("credit_experience", sa.String(20), nullable=False),
        sa.Column("financial_goal", sa.String(50), nullable=False),
        sa.Column("spending_weakness", sa.String(50), nullable=False),
        sa.Column("stress_level", sa.Integer(), nullable=False),
        sa.Column("pays_full_balance", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("age_range IN ('18-22','23-29','30-39','40+')", name="ck_profile_age_range"),
        sa.CheckConstraint("stress_level BETWEEN 1 AND 5", name="ck_profile_stress_level"),
        sa.CheckConstraint("billing_cycle_day BETWEEN 1 AND 28", name="ck_profile_billing_cycle"),
        sa.CheckConstraint("credit_limit > 0", name="ck_profile_credit_limit"),
    )

    # ── transactions ───────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("raw_category", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("ai_category", sa.String(100), nullable=True),
        sa.Column("ai_nudge", sa.String(500), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source IN ('synthetic','plaid','stripe')", name="ck_txn_source"),
        sa.CheckConstraint("priority IN ('essential','semi-essential','discretionary')", name="ck_txn_priority"),
        sa.CheckConstraint("amount > 0", name="ck_txn_amount"),
        sa.CheckConstraint("currency = lower(currency)", name="ck_txn_currency"),
        sa.UniqueConstraint("user_id", "external_id", "source", name="uq_transaction_source"),
    )
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "date"])

    # ── merchant_overrides ─────────────────────────────────────────────────
    op.create_table(
        "merchant_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("merchant_name", sa.String(255), nullable=False),
        sa.Column("preferred_category", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "merchant_name", name="uq_merchant_override"),
    )

    # ── goals ──────────────────────────────────────────────────────────────
    op.create_table(
        "goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("goal_type", sa.String(30), nullable=False),
        sa.Column("target_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("current_amount", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("linked_category", sa.String(100), nullable=True),
        sa.Column("icon", sa.String(10), nullable=True, server_default="🎯"),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("auto_deposit_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("auto_deposit_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("goal_type IN ('travel','purchase','emergency_fund','debt_paydown','savings','custom')", name="ck_goal_type"),
        sa.CheckConstraint("status IN ('active','completed','paused','abandoned')", name="ck_goal_status"),
        sa.CheckConstraint("target_amount > 0", name="ck_goal_target"),
        sa.CheckConstraint("current_amount >= 0", name="ck_goal_current"),
        sa.CheckConstraint("auto_deposit_amount IS NULL OR auto_deposit_amount > 0", name="ck_goal_auto_deposit"),
    )

    # ── goal_progress_snapshots ────────────────────────────────────────────
    op.create_table(
        "goal_progress_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("goal_id", UUID(as_uuid=True), sa.ForeignKey("goals.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("amount_saved", sa.Numeric(10, 2), nullable=False),
        sa.Column("delta", sa.Numeric(10, 2), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source IN ('manual','auto_category','auto_surplus','recap_deposit')", name="ck_snapshot_source"),
        sa.CheckConstraint("amount_saved >= 0", name="ck_snapshot_amount"),
    )
    op.create_index("ix_goal_progress_goal_date", "goal_progress_snapshots", ["goal_id", "recorded_date"])

    # ── achievements ───────────────────────────────────────────────────────
    op.create_table(
        "achievements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("icon", sa.String(10), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("trigger_condition", sa.String(100), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("category IN ('spending','credit','goals','streak','learning')", name="ck_achievement_category"),
        sa.CheckConstraint("points > 0", name="ck_achievement_points"),
    )

    # ── user_achievements ──────────────────────────────────────────────────
    op.create_table(
        "user_achievements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("achievement_id", UUID(as_uuid=True), sa.ForeignKey("achievements.id"), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), nullable=False),
        sa.Column("context", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    # ── nudges ─────────────────────────────────────────────────────────────
    op.create_table(
        "nudges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nudge_type", sa.String(30), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("related_goal_id", UUID(as_uuid=True), sa.ForeignKey("goals.id"), nullable=True),
        sa.Column("related_transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("shown_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("feedback", sa.String(20), nullable=True),
        sa.Column("feedback_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "nudge_type IN ('goal_progress','spending_alert','achievement','weekly_tip','credit_education','education_card')",
            name="ck_nudge_type"
        ),
        sa.CheckConstraint(
            "feedback IN ('helpful','not_helpful') OR feedback IS NULL",
            name="ck_nudge_feedback"
        ),
    )
    op.create_index("ix_nudges_user_shown", "nudges", ["user_id", "shown_at"])

    # ── education_cards ────────────────────────────────────────────────────
    op.create_table(
        "education_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trigger_key", sa.String(100), nullable=False, unique=True),
        sa.Column("trigger_condition", sa.String(300), nullable=False),
        sa.Column("concept", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ── user_education_cards ───────────────────────────────────────────────
    op.create_table(
        "user_education_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("card_id", UUID(as_uuid=True), sa.ForeignKey("education_cards.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("one_action", sa.String(300), nullable=False),
        sa.Column("one_number", sa.String(100), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(), nullable=True),
        sa.Column("was_helpful", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("user_education_cards")
    op.drop_table("education_cards")
    op.drop_index("ix_nudges_user_shown", table_name="nudges")
    op.drop_table("nudges")
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_index("ix_goal_progress_goal_date", table_name="goal_progress_snapshots")
    op.drop_table("goal_progress_snapshots")
    op.drop_table("goals")
    op.drop_table("merchant_overrides")
    op.drop_index("ix_transactions_user_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("user_profiles")
    op.drop_table("users")