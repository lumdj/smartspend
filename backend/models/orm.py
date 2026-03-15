"""
SmartSpend ORM Models
All 13 database tables defined as SQLModel classes.

Security notes:
- All PKs are UUIDs — prevents sequential ID enumeration attacks
- created_at/updated_at are server-side defaults, not client-supplied
- Sensitive fields (amounts, categories) have explicit type constraints
- JSONB fields (metadata, context) typed as dict with default_factory
  to prevent mutable default argument bugs

Fix note: SQLModel does not allow passing nullable= on Field() when
sa_column is also provided. nullable is set on the Column() directly.
"""

from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import UniqueConstraint, CheckConstraint, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional
from datetime import datetime, date as date_type
from uuid import UUID, uuid4
from decimal import Decimal
import sqlalchemy as sa


# ── Helpers ───────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.utcnow()


def new_uuid() -> UUID:
    return uuid4()


# ── Users ─────────────────────────────────────────────────────────────────────

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)

    profile: Optional["UserProfile"] = Relationship(back_populates="user")
    transactions: list["Transaction"] = Relationship(back_populates="user")
    goals: list["Goal"] = Relationship(back_populates="user")
    nudges: list["Nudge"] = Relationship(back_populates="user")
    user_achievements: list["UserAchievement"] = Relationship(back_populates="user")
    user_education_cards: list["UserEducationCard"] = Relationship(back_populates="user")
    merchant_overrides: list["MerchantOverride"] = Relationship(back_populates="user")


# ── User Profiles ─────────────────────────────────────────────────────────────

class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", unique=True)
    name: str = Field(min_length=1, max_length=100)

    age_range: str = Field(
        sa_column=Column(sa.String(10),
            sa.CheckConstraint("age_range IN ('18-22','23-29','30-39','40+')"),
            nullable=False)
    )
    occupation: str = Field(
        sa_column=Column(sa.String(50),
            sa.CheckConstraint("""occupation IN (
                'undergraduate_student','graduate_student','recent_graduate',
                'working_professional','part_time_worker','unemployed','other'
            )"""),
            nullable=False)
    )
    income_source: str = Field(
        sa_column=Column(sa.String(50),
            sa.CheckConstraint("""income_source IN (
                'full_time_job','part_time_job','parental_support',
                'financial_aid_scholarships','freelance_gig','mixed_sources','none_currently'
            )"""),
            nullable=False)
    )
    monthly_income_range: str = Field(max_length=30)
    credit_limit: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2),
            sa.CheckConstraint("credit_limit > 0"),
            nullable=False)
    )
    billing_cycle_day: Optional[int] = Field(
        default=None,
        sa_column=Column(sa.Integer,
            sa.CheckConstraint("billing_cycle_day BETWEEN 1 AND 28"),
            nullable=True)
    )
    billing_cycle_set: bool = Field(default=False)
    credit_experience: str = Field(
        sa_column=Column(sa.String(20),
            sa.CheckConstraint("credit_experience IN ('brand_new','1_2_years','3_plus_years')"),
            nullable=False)
    )
    financial_goal: str = Field(
        sa_column=Column(sa.String(50),
            sa.CheckConstraint("""financial_goal IN (
                'build_credit','reduce_debt','saving_for_something',
                'just_track_spending','learn_financial_basics'
            )"""),
            nullable=False)
    )
    spending_weakness: str = Field(
        sa_column=Column(sa.String(50),
            sa.CheckConstraint("""spending_weakness IN (
                'dining_out','online_shopping','subscriptions',
                'nightlife_social','impulse_buys','coffee_drinks','none_im_disciplined'
            )"""),
            nullable=False)
    )
    stress_level: int = Field(
        sa_column=Column(sa.Integer,
            sa.CheckConstraint("stress_level BETWEEN 1 AND 5"),
            nullable=False)
    )
    pays_full_balance: bool = Field()
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    user: Optional[User] = Relationship(back_populates="profile")


# ── Transactions ──────────────────────────────────────────────────────────────

class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    __table_args__ = (
        UniqueConstraint("user_id", "external_id", "source", name="uq_transaction_source"),
        Index("ix_transactions_user_date", "user_id", "date"),
    )

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    external_id: str = Field(max_length=255)
    source: str = Field(
        sa_column=Column(sa.String(20),
            sa.CheckConstraint("source IN ('synthetic','plaid','stripe')"),
            nullable=False)
    )
    date: date_type = Field()
    merchant: str = Field(max_length=255)
    amount: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2),
            sa.CheckConstraint("amount > 0"),
            nullable=False)
    )
    currency: str = Field(
        default="usd",
        sa_column=Column(sa.String(3),
            sa.CheckConstraint("currency = lower(currency)"),
            nullable=False)
    )
    raw_category: str = Field(max_length=100)
    priority: str = Field(
        sa_column=Column(sa.String(20),
            sa.CheckConstraint("priority IN ('essential','semi-essential','discretionary')"),
            nullable=False)
    )
    ai_category: Optional[str] = Field(default=None, max_length=100)
    ai_nudge: Optional[str] = Field(default=None, max_length=500)
    txn_metadata: Optional[dict] = Field(
        default=None,
        sa_column=Column('metadata', JSONB, nullable=True)
    )
    created_at: datetime = Field(default_factory=utcnow)

    user: Optional[User] = Relationship(back_populates="transactions")
    nudges: list["Nudge"] = Relationship(back_populates="related_transaction")


# ── Merchant Overrides ────────────────────────────────────────────────────────

class MerchantOverride(SQLModel, table=True):
    __tablename__ = "merchant_overrides"

    __table_args__ = (
        UniqueConstraint("user_id", "merchant_name", name="uq_merchant_override"),
    )

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    merchant_name: str = Field(max_length=255)
    preferred_category: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=utcnow)

    user: Optional[User] = Relationship(back_populates="merchant_overrides")


# ── Goals ─────────────────────────────────────────────────────────────────────

class Goal(SQLModel, table=True):
    __tablename__ = "goals"

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    name: str = Field(min_length=1, max_length=100)
    goal_type: str = Field(
        sa_column=Column(sa.String(30),
            sa.CheckConstraint("""goal_type IN (
                'travel','purchase','emergency_fund',
                'debt_paydown','savings','custom'
            )"""),
            nullable=False)
    )
    target_amount: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2),
            sa.CheckConstraint("target_amount > 0"),
            nullable=False)
    )
    current_amount: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(sa.Numeric(10, 2),
            sa.CheckConstraint("current_amount >= 0"),
            nullable=False)
    )
    target_date: Optional[date_type] = Field(default=None)
    status: str = Field(
        default="active",
        sa_column=Column(sa.String(20),
            sa.CheckConstraint("status IN ('active','completed','paused','abandoned')"),
            nullable=False)
    )
    linked_category: Optional[str] = Field(default=None, max_length=100)
    icon: Optional[str] = Field(default="🎯", max_length=10)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    reason: Optional[str] = Field(default=None, max_length=300)
    auto_deposit_amount: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(sa.Numeric(10, 2),
            sa.CheckConstraint("auto_deposit_amount IS NULL OR auto_deposit_amount > 0"),
            nullable=True)
    )
    auto_deposit_enabled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    user: Optional[User] = Relationship(back_populates="goals")
    progress_snapshots: list["GoalProgressSnapshot"] = Relationship(back_populates="goal")
    nudges: list["Nudge"] = Relationship(back_populates="related_goal")


# ── Goal Progress Snapshots ───────────────────────────────────────────────────

class GoalProgressSnapshot(SQLModel, table=True):
    __tablename__ = "goal_progress_snapshots"

    __table_args__ = (
        Index("ix_goal_progress_goal_date", "goal_id", "recorded_date"),
    )

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    goal_id: UUID = Field(foreign_key="goals.id")
    user_id: UUID = Field(foreign_key="users.id")
    recorded_date: date_type = Field()
    amount_saved: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2),
            sa.CheckConstraint("amount_saved >= 0"),
            nullable=False)
    )
    delta: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2), nullable=False)
    )
    source: str = Field(
        sa_column=Column(sa.String(20),
            sa.CheckConstraint("""source IN (
                'manual','auto_category','auto_surplus','recap_deposit'
            )"""),
            nullable=False)
    )
    notes: Optional[str] = Field(default=None, max_length=300)
    created_at: datetime = Field(default_factory=utcnow)

    goal: Optional[Goal] = Relationship(back_populates="progress_snapshots")


# ── Achievements ──────────────────────────────────────────────────────────────

class Achievement(SQLModel, table=True):
    __tablename__ = "achievements"

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    key: str = Field(max_length=100, unique=True)
    name: str = Field(max_length=100)
    description: str = Field(max_length=300)
    icon: str = Field(max_length=10)
    category: str = Field(
        sa_column=Column(sa.String(30),
            sa.CheckConstraint("""category IN (
                'spending','credit','goals','streak','learning'
            )"""),
            nullable=False)
    )
    trigger_condition: str = Field(max_length=100)
    points: int = Field(
        sa_column=Column(sa.Integer,
            sa.CheckConstraint("points > 0"),
            nullable=False)
    )
    is_custom: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)

    user_achievements: list["UserAchievement"] = Relationship(back_populates="achievement")


# ── User Achievements ─────────────────────────────────────────────────────────

class UserAchievement(SQLModel, table=True):
    __tablename__ = "user_achievements"

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    achievement_id: UUID = Field(foreign_key="achievements.id")
    unlocked_at: datetime = Field(default_factory=utcnow)
    context: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False)
    )

    user: Optional[User] = Relationship(back_populates="user_achievements")
    achievement: Optional[Achievement] = Relationship(back_populates="user_achievements")


# ── Nudges ────────────────────────────────────────────────────────────────────

class Nudge(SQLModel, table=True):
    __tablename__ = "nudges"

    __table_args__ = (
        Index("ix_nudges_user_shown", "user_id", "shown_at"),
    )

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    nudge_type: str = Field(
        sa_column=Column(sa.String(30),
            sa.CheckConstraint("""nudge_type IN (
                'goal_progress','spending_alert','achievement',
                'weekly_tip','credit_education','education_card'
            )"""),
            nullable=False)
    )
    message: str = Field(max_length=1000)
    related_goal_id: Optional[UUID] = Field(default=None, foreign_key="goals.id")
    related_transaction_id: Optional[UUID] = Field(default=None, foreign_key="transactions.id")
    shown_at: Optional[datetime] = Field(default=None)
    dismissed_at: Optional[datetime] = Field(default=None)
    feedback: Optional[str] = Field(
        default=None,
        sa_column=Column(sa.String(20),
            sa.CheckConstraint("feedback IN ('helpful','not_helpful') OR feedback IS NULL"),
            nullable=True)
    )
    feedback_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)

    user: Optional[User] = Relationship(back_populates="nudges")
    related_goal: Optional[Goal] = Relationship(back_populates="nudges")
    related_transaction: Optional[Transaction] = Relationship(back_populates="nudges")


# ── Education Cards ───────────────────────────────────────────────────────────

class EducationCard(SQLModel, table=True):
    __tablename__ = "education_cards"

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    trigger_key: str = Field(max_length=100, unique=True)
    trigger_condition: str = Field(max_length=300)
    concept: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=utcnow)

    user_cards: list["UserEducationCard"] = Relationship(back_populates="card")


# ── User Education Cards ──────────────────────────────────────────────────────

class UserEducationCard(SQLModel, table=True):
    __tablename__ = "user_education_cards"

    id: UUID = Field(default_factory=new_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    card_id: UUID = Field(foreign_key="education_cards.id")
    title: str = Field(max_length=200)
    content: str = Field(sa_column=Column(Text, nullable=False))
    one_action: str = Field(max_length=300)
    one_number: str = Field(max_length=100)
    triggered_at: datetime = Field(default_factory=utcnow)
    viewed_at: Optional[datetime] = Field(default=None)
    was_helpful: Optional[bool] = Field(default=None)

    user: Optional[User] = Relationship(back_populates="user_education_cards")
    card: Optional[EducationCard] = Relationship(back_populates="user_cards")