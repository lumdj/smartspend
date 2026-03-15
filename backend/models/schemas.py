"""
SmartSpend Pydantic Schemas
Request/response models for the API layer.

These are deliberately separate from the ORM models in orm.py.
ORM models define the database shape.
Schemas define what the API accepts and returns.

This separation means:
- You control exactly what fields are exposed to clients
- Internal fields (created_at, metadata) stay internal unless explicitly included
- Input validation happens at the API boundary before anything hits the DB
- You can evolve the DB schema without breaking the API contract

Security notes:
- All string inputs have max_length constraints
- Numeric inputs have gt/ge constraints — no negative amounts through the API
- Enum fields use Python Enum classes — invalid values rejected by Pydantic
- No password or credential fields — auth is out of scope for v1
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum
import bleach


# ── Shared Validators ─────────────────────────────────────────────────────────

def sanitize_text(value: str) -> str:
    """Strip HTML/script tags from any user-supplied text field."""
    return bleach.clean(value, tags=[], strip=True).strip()


# ── Enums ─────────────────────────────────────────────────────────────────────

class AgeRange(str, Enum):
    range_18_22 = "18-22"
    range_23_29 = "23-29"
    range_30_39 = "30-39"
    range_40_plus = "40+"


class OccupationStatus(str, Enum):
    undergrad = "undergraduate_student"
    grad = "graduate_student"
    recent_grad = "recent_graduate"
    working = "working_professional"
    part_time = "part_time_worker"
    unemployed = "unemployed"
    other = "other"


class IncomeSource(str, Enum):
    full_time = "full_time_job"
    part_time = "part_time_job"
    parental = "parental_support"
    financial_aid = "financial_aid_scholarships"
    freelance = "freelance_gig"
    mixed = "mixed_sources"
    none = "none_currently"


class CreditExperience(str, Enum):
    brand_new = "brand_new"
    one_to_two = "1_2_years"
    three_plus = "3_plus_years"


class FinancialGoal(str, Enum):
    build_credit = "build_credit"
    reduce_debt = "reduce_debt"
    save_goal = "saving_for_something"
    track_spending = "just_track_spending"
    learn_basics = "learn_financial_basics"


class SpendingWeakness(str, Enum):
    dining = "dining_out"
    shopping = "online_shopping"
    subscriptions = "subscriptions"
    nightlife = "nightlife_social"
    impulse = "impulse_buys"
    coffee = "coffee_drinks"
    none = "none_im_disciplined"


class GoalType(str, Enum):
    travel = "travel"
    purchase = "purchase"
    emergency_fund = "emergency_fund"
    debt_paydown = "debt_paydown"
    savings = "savings"
    custom = "custom"


class GoalStatus(str, Enum):
    active = "active"
    completed = "completed"
    paused = "paused"
    abandoned = "abandoned"


class NudgeType(str, Enum):
    goal_progress = "goal_progress"
    spending_alert = "spending_alert"
    achievement = "achievement"
    weekly_tip = "weekly_tip"
    credit_education = "credit_education"
    education_card = "education_card"


class NudgeFeedback(str, Enum):
    helpful = "helpful"
    not_helpful = "not_helpful"


class ProgressSource(str, Enum):
    manual = "manual"
    auto_category = "auto_category"
    auto_surplus = "auto_surplus"
    recap_deposit = "recap_deposit"


# ── User / Profile Schemas ────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Request body for creating a new user + profile in one step (onboarding)."""

    # Identity
    name: str = Field(min_length=1, max_length=100)

    # Demographics
    age_range: AgeRange
    occupation: OccupationStatus
    income_source: IncomeSource
    monthly_income_range: str = Field(min_length=1, max_length=30)
    credit_limit: Decimal = Field(gt=0, le=100000)

    # Billing cycle — optional
    billing_cycle_day: Optional[int] = Field(default=None, ge=1, le=28)

    # Credit + behavior
    credit_experience: CreditExperience
    financial_goal: FinancialGoal
    spending_weakness: SpendingWeakness
    stress_level: int = Field(ge=1, le=5)
    pays_full_balance: bool

    # Demo persona — which synthetic data profile to load
    persona_key: Optional[str] = Field(default="alex", max_length=20)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v)

    @field_validator("monthly_income_range")
    @classmethod
    def sanitize_income_range(cls, v: str) -> str:
        return sanitize_text(v)

    @field_validator("persona_key")
    @classmethod
    def validate_persona(cls, v: Optional[str]) -> Optional[str]:
        valid = {"alex", "jordan", "taylor"}
        if v and v not in valid:
            raise ValueError(f"persona_key must be one of {valid}")
        return v


class UserProfileResponse(BaseModel):
    """Full profile returned to the client."""
    user_id: UUID
    name: str
    age_range: str
    occupation: str
    income_source: str
    monthly_income_range: str
    credit_limit: Decimal
    billing_cycle_day: Optional[int]
    billing_cycle_set: bool
    credit_experience: str
    financial_goal: str
    spending_weakness: str
    stress_level: int
    pays_full_balance: bool
    created_at: datetime
    updated_at: datetime

    # Derived — computed by the API, not stored
    tone_profile: str

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """Partial update — all fields optional, only provided fields are changed."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    income_source: Optional[IncomeSource] = None
    monthly_income_range: Optional[str] = Field(default=None, max_length=30)
    credit_limit: Optional[Decimal] = Field(default=None, gt=0, le=100000)
    billing_cycle_day: Optional[int] = Field(default=None, ge=1, le=28)
    financial_goal: Optional[FinancialGoal] = None
    spending_weakness: Optional[SpendingWeakness] = None
    stress_level: Optional[int] = Field(default=None, ge=1, le=5)
    pays_full_balance: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v) if v else v


class BillingCycleUpdate(BaseModel):
    billing_cycle_day: int = Field(ge=1, le=28)


# ── Transaction Schemas ───────────────────────────────────────────────────────

class TransactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    merchant: str
    amount: Decimal
    currency: str
    raw_category: str
    priority: str
    ai_category: Optional[str]
    ai_nudge: Optional[str]
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    page: int
    per_page: int


class MerchantOverrideCreate(BaseModel):
    merchant_name: str = Field(min_length=1, max_length=255)
    preferred_category: str = Field(min_length=1, max_length=100)

    @field_validator("merchant_name", "preferred_category")
    @classmethod
    def sanitize(cls, v: str) -> str:
        return sanitize_text(v)


# ── Goal Schemas ──────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    goal_type: GoalType
    target_amount: Decimal = Field(gt=0, le=1000000)
    target_date: Optional[date] = None
    linked_category: Optional[str] = Field(default=None, max_length=100)
    icon: Optional[str] = Field(default="🎯", max_length=10)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    reason: Optional[str] = Field(default=None, max_length=300)
    auto_deposit_amount: Optional[Decimal] = Field(default=None, gt=0, le=100000)
    auto_deposit_enabled: bool = False

    @field_validator("name", "reason")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v) if v else v

    @field_validator("target_date")
    @classmethod
    def validate_future_date(cls, v: Optional[date]) -> Optional[date]:
        if v and v <= date.today():
            raise ValueError("target_date must be in the future")
        return v

    @model_validator(mode="after")
    def validate_auto_deposit(self) -> "GoalCreate":
        if self.auto_deposit_enabled and not self.auto_deposit_amount:
            raise ValueError(
                "auto_deposit_amount is required when auto_deposit_enabled is True"
            )
        return self


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    target_amount: Optional[Decimal] = Field(default=None, gt=0, le=1000000)
    target_date: Optional[date] = None
    status: Optional[GoalStatus] = None
    linked_category: Optional[str] = Field(default=None, max_length=100)
    icon: Optional[str] = Field(default=None, max_length=10)
    reason: Optional[str] = Field(default=None, max_length=300)
    auto_deposit_amount: Optional[Decimal] = Field(default=None, gt=0)
    auto_deposit_enabled: Optional[bool] = None

    @field_validator("name", "reason")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v) if v else v


class GoalProgressCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=100000)
    source: ProgressSource = ProgressSource.manual
    notes: Optional[str] = Field(default=None, max_length=300)
    recorded_date: Optional[date] = None

    @field_validator("notes")
    @classmethod
    def sanitize_notes(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v) if v else v


class GoalResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    goal_type: str
    target_amount: Decimal
    current_amount: Decimal
    target_date: Optional[date]
    status: str
    linked_category: Optional[str]
    icon: Optional[str]
    reason: Optional[str]
    auto_deposit_enabled: bool
    progress_pct: float      # Computed: current / target * 100
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalListResponse(BaseModel):
    goals: list[GoalResponse]
    active_count: int
    max_active: int = 3


# ── Nudge Schemas ─────────────────────────────────────────────────────────────

class NudgeResponse(BaseModel):
    id: UUID
    nudge_type: str
    message: str
    related_goal_id: Optional[UUID]
    related_transaction_id: Optional[UUID]
    shown_at: Optional[datetime]
    dismissed_at: Optional[datetime]
    feedback: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NudgeFeedbackUpdate(BaseModel):
    feedback: NudgeFeedback


# ── Achievement Schemas ───────────────────────────────────────────────────────

class AchievementResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str
    icon: str
    category: str
    points: int
    unlocked: bool           # Whether this user has earned it
    unlocked_at: Optional[datetime]
    context: Optional[dict]

    model_config = {"from_attributes": True}


# ── Insights / Analytics Schemas ──────────────────────────────────────────────

class SpendingSummary(BaseModel):
    user_id: UUID
    period_start: date
    period_end: date
    total_spend: Decimal
    essential_spend: Decimal
    semi_essential_spend: Decimal
    discretionary_spend: Decimal
    utilization_rate: float       # % of credit limit
    income_spend_ratio: float     # % of monthly income
    transaction_count: int
    top_categories: list[dict]    # [{"category": str, "amount": Decimal}]
    vs_last_period: Optional[dict]  # delta comparisons


class AlertResponse(BaseModel):
    alert_type: str
    severity: str              # 'info' | 'warning' | 'critical'
    category: Optional[str]
    message: str
    amount: Optional[Decimal]
    threshold: Optional[Decimal]


class InsightResponse(BaseModel):
    user_id: UUID
    summary: SpendingSummary
    alerts: list[AlertResponse]
    health_score: int
    recommendations: list[str]
    credit_education_tip: str


class MonthlyReportResponse(BaseModel):
    user_id: UUID
    user_name: str
    month: str                 # YYYY-MM
    health_score: int
    summary: SpendingSummary
    alerts: list[AlertResponse]
    ai_narrative: str
    action_items: list[str]
    badges_earned: list[str]
    biggest_risk: Optional[str]
    available_months: list[str]


# ── Education Card Schemas ────────────────────────────────────────────────────

class EducationCardResponse(BaseModel):
    id: UUID
    card_id: UUID
    trigger_key: str
    title: str
    content: str               # May contain [[term|definition]] markup
    one_action: str
    one_number: str
    triggered_at: datetime
    viewed_at: Optional[datetime]
    was_helpful: Optional[bool]

    model_config = {"from_attributes": True}


# ── Demo Control Panel Schemas ────────────────────────────────────────────────

class DemoLoadPersona(BaseModel):
    persona_key: str = Field(min_length=1, max_length=20)
    user_id: UUID

    @field_validator("persona_key")
    @classmethod
    def validate_persona(cls, v: str) -> str:
        if v not in {"alex", "jordan", "taylor"}:
            raise ValueError("persona_key must be alex, jordan, or taylor")
        return v


class DemoTriggerEvent(BaseModel):
    user_id: UUID
    event_type: str = Field(min_length=1, max_length=50)
    parameters: Optional[dict] = Field(default_factory=dict)


# ── Generic Response Wrappers ─────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Simple success/info message response."""
    message: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    adapter: str
    adapter_healthy: bool
    environment: str
