"""
SmartSpend Achievements Service

Evaluates achievement trigger conditions against current user state
and unlocks achievements when conditions are met.

Design: rule-based triggers evaluated after analytics computation.
Claude writes the congratulatory message — the service handles the logic.
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Session, select

from models.orm import Achievement, UserAchievement, Nudge

logger = logging.getLogger(__name__)


# ── Trigger Evaluation ────────────────────────────────────────────────────────

def evaluate_and_unlock(
    session: Session,
    user_id: UUID,
    summary: dict,
    alerts: list[dict],
    goals: list,
    context: dict,
) -> list[Achievement]:
    """
    Evaluate all achievement trigger conditions for a user.
    Unlocks any that are newly met and not already earned.

    Args:
        session: DB session
        user_id: User to evaluate
        summary: Spending summary from analytics service
        alerts: Alert list from alerts service
        goals: List of user's Goal ORM objects
        context: Additional context dict (e.g. stress_level, months_active)

    Returns:
        List of newly unlocked Achievement objects
    """
    # Load all achievements and which ones this user already has
    all_achievements = session.exec(select(Achievement)).all()
    earned_keys = {
        ua.achievement.key
        for ua in session.exec(
            select(UserAchievement).where(
                UserAchievement.user_id == user_id
            )
        ).all()
        if ua.achievement
    }

    newly_unlocked = []

    for achievement in all_achievements:
        if achievement.key in earned_keys:
            continue  # Already earned — skip

        trigger_context = _build_trigger_context(
            achievement.key, summary, alerts, goals, context
        )

        if trigger_context is not None:
            unlocked = _unlock_achievement(
                session, user_id, achievement, trigger_context
            )
            if unlocked:
                newly_unlocked.append(achievement)

    if newly_unlocked:
        session.commit()
        logger.info(
            f"Unlocked {len(newly_unlocked)} achievements for user {user_id}: "
            f"{[a.key for a in newly_unlocked]}"
        )

    return newly_unlocked


def _build_trigger_context(
    key: str,
    summary: dict,
    alerts: list[dict],
    goals: list,
    context: dict,
) -> dict | None:
    """
    Returns a context dict if the achievement condition is met, None if not.
    The context is stored in user_achievements.context for display/audit.
    """

    util = summary.get("utilization_rate", 100)
    income_ratio = summary.get("income_spend_ratio", 100)
    total = float(summary.get("total_spend", 0))
    income = float(context.get("monthly_income", 1500))
    active_goals = [g for g in goals if g.status == "active"]
    completed_goals = [g for g in goals if g.status == "completed"]

    # ── Credit achievements ───────────────────────────────────────────────
    if key == "credit_conscious":
        if util < 30:
            return {"utilization": util, "month": context.get("month")}

    if key == "danger_zone_avoided":
        prev_util = context.get("prev_utilization", 0)
        if prev_util >= 70 and util < 50:
            return {"prev_utilization": prev_util, "current_utilization": util}

    if key == "debt_dodger":
        consecutive_months = context.get("full_balance_months", 0)
        if consecutive_months >= 3:
            return {"consecutive_months": consecutive_months}

    if key == "first_full_balance":
        if context.get("paid_full_balance_this_month") and \
           context.get("full_balance_months", 0) == 1:
            return {"month": context.get("month")}

    # ── Spending achievements ─────────────────────────────────────────────
    if key == "under_budget":
        if income_ratio < 80:
            return {"income_ratio": income_ratio, "month": context.get("month")}

    if key == "dining_detective":
        weeks_reduced = context.get("dining_reduced_weeks", 0)
        if weeks_reduced >= 3:
            return {"weeks_reduced": weeks_reduced}

    if key == "subscription_audit":
        sub_count = context.get("subscription_count", 99)
        if sub_count < 3:
            return {"subscription_count": sub_count}

    # ── Goal achievements ─────────────────────────────────────────────────
    if key == "first_goal":
        if len(goals) >= 1:
            return {"goal_name": goals[0].name}

    if key == "goal_halfway":
        for goal in active_goals:
            if goal.target_amount > 0:
                pct = float(goal.current_amount / goal.target_amount * 100)
                if pct >= 50:
                    return {"goal_name": goal.name, "progress_pct": round(pct, 1)}

    if key == "goal_crusher":
        if completed_goals:
            g = completed_goals[0]
            return {
                "goal_name": g.name,
                "target_amount": float(g.target_amount),
            }

    if key == "three_goals":
        if len(active_goals) >= 3:
            return {"goal_names": [g.name for g in active_goals]}

    # ── Streak achievements ───────────────────────────────────────────────
    if key == "streak_7":
        if context.get("login_streak", 0) >= 7:
            return {"streak_days": context.get("login_streak")}

    if key == "streak_30":
        if context.get("login_streak", 0) >= 30:
            return {"streak_days": context.get("login_streak")}

    # ── Learning achievements ─────────────────────────────────────────────
    if key == "knowledge_seeker":
        if context.get("education_cards_viewed", 0) >= 5:
            return {"cards_viewed": context.get("education_cards_viewed")}

    if key == "stress_drop":
        stress_drop = context.get("stress_level_drop", 0)
        if stress_drop >= 2:
            return {
                "prev_stress": context.get("prev_stress_level"),
                "current_stress": context.get("current_stress_level"),
            }

    return None  # Condition not met


def _unlock_achievement(
    session: Session,
    user_id: UUID,
    achievement: Achievement,
    trigger_context: dict,
) -> bool:
    """
    Record the achievement unlock and queue a nudge.
    Returns True if unlocked, False if already exists (race condition guard).
    """
    # Double-check it doesn't already exist
    existing = session.exec(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
        )
    ).first()

    if existing:
        return False

    user_achievement = UserAchievement(
        id=uuid4(),
        user_id=user_id,
        achievement_id=achievement.id,
        unlocked_at=datetime.utcnow(),
        context=trigger_context,
    )
    session.add(user_achievement)

    # Queue an achievement nudge
    nudge = Nudge(
        id=uuid4(),
        user_id=user_id,
        nudge_type="achievement",
        message=(
            f"{achievement.icon} Achievement unlocked: **{achievement.name}** — "
            f"{achievement.description} (+{achievement.points} pts)"
        ),
        created_at=datetime.utcnow(),
    )
    session.add(nudge)
    return True


# ── Queries ───────────────────────────────────────────────────────────────────

def get_user_achievements_with_catalog(
    session: Session,
    user_id: UUID,
) -> list[dict]:
    """
    Return the full achievement catalog with earned/unearned status for a user.
    Used by the Achievements page.
    """
    all_achievements = session.exec(
        select(Achievement).order_by(Achievement.category, Achievement.points)
    ).all()

    earned_map = {
        ua.achievement_id: ua
        for ua in session.exec(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        ).all()
    }

    result = []
    for a in all_achievements:
        ua = earned_map.get(a.id)
        result.append({
            "id": a.id,
            "key": a.key,
            "name": a.name,
            "description": a.description,
            "icon": a.icon,
            "category": a.category,
            "points": a.points,
            "unlocked": ua is not None,
            "unlocked_at": ua.unlocked_at if ua else None,
            "context": ua.context if ua else None,
        })

    return result


def get_total_points(session: Session, user_id: UUID) -> int:
    """Return total achievement points earned by a user."""
    earned = session.exec(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    ).all()

    total = 0
    for ua in earned:
        achievement = session.get(Achievement, ua.achievement_id)
        if achievement:
            total += achievement.points
    return total
