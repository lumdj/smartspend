"""
SmartSpend Profile Router

Handles user creation (onboarding) and profile management.
This is the first endpoint the frontend calls — it creates the
user record, saves the profile, and triggers initial data ingestion.

Routes:
    POST   /profile/              Create user + profile (onboarding)
    GET    /profile/{user_id}     Get profile
    PATCH  /profile/{user_id}     Update profile fields
    PATCH  /profile/{user_id}/billing-cycle   Set billing cycle day
    GET    /profile/{user_id}/exists          Check if profile exists
    DELETE /profile/{user_id}     Delete user + all data (demo reset)

Security notes:
    - user_id is UUID — not guessable/enumerable
    - All text inputs sanitized via bleach in schemas.py
    - DELETE is hard-coded to cascade — use only for demo reset
    - No authentication in v1 — user_id stored in localStorage on frontend
      Production would add JWT or session-based auth here
"""

import logging
from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from database import get_session
from models.orm import User, UserProfile
from models.schemas import (
    UserCreate,
    UserProfileResponse,
    UserProfileUpdate,
    BillingCycleUpdate,
    MessageResponse,
)
from ingestion.ingester import TransactionIngester

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_or_404(user_id, session: Session) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def _get_profile_or_404(user_id, session: Session) -> UserProfile:
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please complete onboarding.",
        )
    return profile


def _compute_tone_profile(profile: UserProfile) -> str:
    """
    Derives the AI tone setting from stress level and credit experience.
    Kept here (not on the ORM model) to keep the ORM layer clean.
    """
    if profile.stress_level >= 4:
        return "gentle_encouraging"
    if profile.stress_level <= 2 and profile.credit_experience == "3_plus_years":
        return "direct_sassy"
    return "balanced_coaching"


def _profile_to_response(profile: UserProfile) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        age_range=profile.age_range,
        occupation=profile.occupation,
        income_source=profile.income_source,
        monthly_income_range=profile.monthly_income_range,
        credit_limit=profile.credit_limit,
        billing_cycle_day=profile.billing_cycle_day,
        billing_cycle_set=profile.billing_cycle_set,
        credit_experience=profile.credit_experience,
        financial_goal=profile.financial_goal,
        spending_weakness=profile.spending_weakness,
        stress_level=profile.stress_level,
        pays_full_balance=profile.pays_full_balance,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        tone_profile=_compute_tone_profile(profile),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user and profile (onboarding)",
)
def create_profile(
    body: UserCreate,
    db: Session = Depends(get_session),
):
    """
    Creates a new user and their profile in a single transaction.
    Also triggers synthetic data ingestion so the dashboard has
    data immediately after onboarding.

    This is the first API call the frontend makes.
    """
    # Create the bare user record
    user = User(id=uuid4(), created_at=datetime.utcnow())
    db.add(user)
    db.flush()  # Get the ID without committing yet

    # Create the profile
    profile = UserProfile(
        id=uuid4(),
        user_id=user.id,
        name=body.name,
        age_range=body.age_range.value,
        occupation=body.occupation.value,
        income_source=body.income_source.value,
        monthly_income_range=body.monthly_income_range,
        credit_limit=body.credit_limit,
        billing_cycle_day=body.billing_cycle_day,
        billing_cycle_set=body.billing_cycle_day is not None,
        credit_experience=body.credit_experience.value,
        financial_goal=body.financial_goal.value,
        spending_weakness=body.spending_weakness.value,
        stress_level=body.stress_level,
        pays_full_balance=body.pays_full_balance,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(f"Created user {user.id} with profile for '{body.name}'")

    # Ingest synthetic transactions so dashboard has data immediately
    # Done after commit so user/profile exist in DB before ingestion
    try:
        ingester = TransactionIngester(db)
        result = ingester.ingest(
            user_id=user.id,
            persona_key=body.persona_key or "alex",
        )
        logger.info(
            f"Initial ingestion for user {user.id}: "
            f"{result['inserted']} transactions loaded"
        )
    except Exception as e:
        # Non-fatal — user and profile are saved, ingestion can be retried
        logger.error(f"Initial ingestion failed for user {user.id}: {e}")

    return _profile_to_response(profile)


@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    summary="Get user profile",
)
def get_profile(
    user_id: str,
    db: Session = Depends(get_session),
):
    """Retrieve a user's profile. Returns 404 if onboarding not completed."""
    from uuid import UUID
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format — must be a valid UUID",
        )

    _get_user_or_404(uid, db)
    profile = _get_profile_or_404(uid, db)
    return _profile_to_response(profile)


@router.patch(
    "/{user_id}",
    response_model=UserProfileResponse,
    summary="Update profile fields",
)
def update_profile(
    user_id: str,
    body: UserProfileUpdate,
    db: Session = Depends(get_session),
):
    """
    Partial update — only provided fields are changed.
    All fields are optional. Used by Settings → Edit Profile.
    """
    from uuid import UUID
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format",
        )

    _get_user_or_404(uid, db)
    profile = _get_profile_or_404(uid, db)

    # Only update fields that were explicitly provided
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Convert enum values to their string representation
        if hasattr(value, "value"):
            value = value.value
        setattr(profile, field, value)

    profile.updated_at = datetime.utcnow()
    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(f"Updated profile for user {uid}: {list(update_data.keys())}")
    return _profile_to_response(profile)


@router.patch(
    "/{user_id}/billing-cycle",
    response_model=UserProfileResponse,
    summary="Set billing cycle day",
)
def set_billing_cycle(
    user_id: str,
    body: BillingCycleUpdate,
    db: Session = Depends(get_session),
):
    """
    Set or update the billing cycle day (1-28).
    Separate endpoint because this is a distinct UX step —
    users are prompted to set this from the dashboard, not onboarding.
    """
    from uuid import UUID
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format",
        )

    _get_user_or_404(uid, db)
    profile = _get_profile_or_404(uid, db)

    profile.billing_cycle_day = body.billing_cycle_day
    profile.billing_cycle_set = True
    profile.updated_at = datetime.utcnow()

    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(f"Set billing cycle day to {body.billing_cycle_day} for user {uid}")
    return _profile_to_response(profile)


@router.get(
    "/{user_id}/exists",
    response_model=dict,
    summary="Check if profile exists",
)
def profile_exists(
    user_id: str,
    db: Session = Depends(get_session),
):
    """
    Used by the frontend on app load to determine whether to show
    the onboarding flow or the dashboard.

    Returns: {"exists": bool}
    """
    from uuid import UUID
    try:
        uid = UUID(user_id)
    except ValueError:
        return {"exists": False}

    user = db.get(User, uid)
    if not user:
        return {"exists": False}

    profile = db.exec(
        select(UserProfile).where(UserProfile.user_id == uid)
    ).first()

    return {"exists": profile is not None}


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Delete user and all data (demo reset)",
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_session),
):
    """
    Hard delete — removes the user and ALL associated data.
    Intended for demo reset only.

    In production this would require authentication and
    would soft-delete with a deleted_at timestamp instead.
    """
    from uuid import UUID
    from sqlmodel import delete
    from models.orm import (
        Transaction, MerchantOverride, Goal, GoalProgressSnapshot,
        UserAchievement, Nudge, UserEducationCard,
    )

    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format",
        )

    user = db.get(User, uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Delete in dependency order — children before parents
    db.exec(delete(UserEducationCard).where(UserEducationCard.user_id == uid))
    db.exec(delete(Nudge).where(Nudge.user_id == uid))
    db.exec(delete(UserAchievement).where(UserAchievement.user_id == uid))

    # Goal snapshots before goals
    goal_ids = [
        g.id for g in db.exec(select(Goal).where(Goal.user_id == uid)).all()
    ]
    if goal_ids:
        db.exec(
            delete(GoalProgressSnapshot).where(
                GoalProgressSnapshot.goal_id.in_(goal_ids)
            )
        )
    db.exec(delete(Goal).where(Goal.user_id == uid))

    db.exec(delete(MerchantOverride).where(MerchantOverride.user_id == uid))
    db.exec(delete(Transaction).where(Transaction.user_id == uid))
    db.exec(delete(UserProfile).where(UserProfile.user_id == uid))
    db.delete(user)
    db.commit()

    logger.info(f"Deleted user {uid} and all associated data")
    return MessageResponse(
        message="User and all data deleted successfully",
        detail=f"user_id: {uid}",
    )
