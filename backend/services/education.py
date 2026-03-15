"""
SmartSpend Education Service

Detects when education card triggers fire and coordinates
Claude-generated card content. Ensures each user only receives
each card once.

Pipeline:
1. evaluate_triggers() — checks which cards should fire
2. generate_card() — calls Claude for dynamic content
3. store_card() — saves to user_education_cards + queues nudge
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Session, select

from models.orm import EducationCard, UserEducationCard, UserProfile, Nudge

logger = logging.getLogger(__name__)


# ── Trigger Evaluation ────────────────────────────────────────────────────────

def evaluate_triggers(
    session: Session,
    user_id: UUID,
    summary: dict,
    alerts: list[dict],
    goals: list,
    context: dict,
) -> list[str]:
    """
    Check which education card triggers fire for a user.
    Filters out cards the user has already received.

    Returns list of trigger_keys that should fire.
    """
    # Which cards has this user already received?
    received_keys = {
        uec.card.trigger_key
        for uec in session.exec(
            select(UserEducationCard).where(
                UserEducationCard.user_id == user_id
            )
        ).all()
        if uec.card
    }

    util = summary.get("utilization_rate", 0)
    income_ratio = summary.get("income_spend_ratio", 0)
    stress_level = context.get("stress_level", 3)
    active_goals = [g for g in goals if g.status == "active"]
    completed_goals = [g for g in goals if g.status == "completed"]

    fired = []

    def _should_fire(key: str, condition: bool) -> None:
        if condition and key not in received_keys:
            fired.append(key)

    _should_fire("utilization_over_50", util >= 50 and util < 70)
    _should_fire("utilization_over_70", util >= 70)
    _should_fire("first_goal_created", len(goals) >= 1)
    _should_fire(
        "goal_halfway",
        any(
            float(g.current_amount / g.target_amount * 100) >= 50
            for g in active_goals if g.target_amount > 0
        )
    )
    _should_fire("goal_completed", len(completed_goals) >= 1)
    _should_fire(
        "first_full_balance_month",
        context.get("paid_full_balance_this_month") and
        context.get("full_balance_months", 0) == 1
    )
    _should_fire(
        "carrying_balance_detected",
        not context.get("pays_full_balance", True) and
        context.get("months_active", 0) == 1
    )

    dining_amount = next(
        (c["amount"] for c in summary.get("top_categories", [])
         if c["category"] == "dining"),
        0,
    )
    monthly_income = float(context.get("monthly_income", 1500))
    _should_fire(
        "dining_spike",
        monthly_income > 0 and dining_amount > monthly_income * 0.25
    )

    sub_count = context.get("subscription_count", 0)
    _should_fire("subscription_count_high", sub_count >= 4)
    _should_fire("income_overspend", income_ratio >= 90)
    _should_fire("stress_level_high", stress_level == 5)
    _should_fire("first_month_complete", context.get("months_active", 0) == 1)

    return fired


def create_education_card_for_user(
    session: Session,
    user_id: UUID,
    trigger_key: str,
    profile: UserProfile,
    summary: dict,
    context: dict,
    claude_service,  # Injected to avoid circular import
) -> UserEducationCard | None:
    """
    Generate and store an education card for a user.

    Args:
        session: DB session
        user_id: Target user
        trigger_key: Which card to generate
        profile: User's profile (for Claude context)
        summary: Current spending summary
        context: Additional context dict
        claude_service: ClaudeService instance for card generation

    Returns:
        The created UserEducationCard, or None if card definition not found.
    """
    # Look up the card definition
    card_def = session.exec(
        select(EducationCard).where(
            EducationCard.trigger_key == trigger_key
        )
    ).first()

    if not card_def:
        logger.warning(f"No education card found for trigger_key: {trigger_key}")
        return None

    # Double-check the user hasn't already received this card
    existing = session.exec(
        select(UserEducationCard).where(
            UserEducationCard.user_id == user_id,
            UserEducationCard.card_id == card_def.id,
        )
    ).first()

    if existing:
        logger.debug(f"User {user_id} already has card {trigger_key} — skipping")
        return None

    # Generate content via Claude
    try:
        generated = claude_service.generate_education_card(
            trigger_key=trigger_key,
            concept=card_def.concept,
            profile=profile,
            summary=summary,
            context=context,
        )
    except Exception as e:
        logger.error(f"Claude education card generation failed for {trigger_key}: {e}")
        return None

    # Store the card
    user_card = UserEducationCard(
        id=uuid4(),
        user_id=user_id,
        card_id=card_def.id,
        title=generated.get("title", card_def.concept),
        content=generated.get("content", ""),
        one_action=generated.get("one_action", ""),
        one_number=generated.get("one_number", ""),
        triggered_at=datetime.utcnow(),
    )
    session.add(user_card)

    # Queue as a nudge so it surfaces in the notification layer
    nudge = Nudge(
        id=uuid4(),
        user_id=user_id,
        nudge_type="education_card",
        message=f"📚 New: {user_card.title}",
        created_at=datetime.utcnow(),
    )
    session.add(nudge)
    session.commit()

    logger.info(f"Created education card '{trigger_key}' for user {user_id}")
    return user_card


# ── Queries ───────────────────────────────────────────────────────────────────

def get_user_education_cards(
    session: Session,
    user_id: UUID,
    unviewed_only: bool = False,
) -> list[UserEducationCard]:
    """Return education cards for a user, optionally filtered to unviewed."""
    query = select(UserEducationCard).where(
        UserEducationCard.user_id == user_id
    )
    if unviewed_only:
        query = query.where(UserEducationCard.viewed_at.is_(None))

    return session.exec(
        query.order_by(UserEducationCard.triggered_at.desc())
    ).all()


def mark_card_viewed(
    session: Session,
    card_id: UUID,
    user_id: UUID,
) -> UserEducationCard | None:
    """Mark a card as viewed. Returns None if not found."""
    card = session.exec(
        select(UserEducationCard).where(
            UserEducationCard.id == card_id,
            UserEducationCard.user_id == user_id,
        )
    ).first()

    if not card:
        return None

    card.viewed_at = datetime.utcnow()
    session.add(card)
    session.commit()
    return card


def submit_card_feedback(
    session: Session,
    card_id: UUID,
    user_id: UUID,
    was_helpful: bool,
) -> UserEducationCard | None:
    """Record user feedback on an education card."""
    card = session.exec(
        select(UserEducationCard).where(
            UserEducationCard.id == card_id,
            UserEducationCard.user_id == user_id,
        )
    ).first()

    if not card:
        return None

    card.was_helpful = was_helpful
    if not card.viewed_at:
        card.viewed_at = datetime.utcnow()

    session.add(card)
    session.commit()
    return card
