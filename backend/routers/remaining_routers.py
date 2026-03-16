"""
SmartSpend — Remaining Routers
insights.py, reports.py, goals.py, nudges.py, achievements.py, demo.py
All in one file for Phase 4 — split into separate files as the project grows.
"""

# ─────────────────────────────────────────────────────────────────────────────
# INSIGHTS ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from uuid import UUID
from typing import Optional
from datetime import datetime
import logging

from database import get_session
from models.orm import User, UserProfile
from models.schemas import InsightResponse, MonthlyReportResponse, MessageResponse
from services import analytics, alerts as alerts_svc
from services.claude_service import ClaudeService, get_claude_service

logger = logging.getLogger(__name__)


def _uid(user_id: str) -> UUID:
    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")


def _get_profile(uid: UUID, db: Session) -> UserProfile:
    profile = db.exec(
        select(UserProfile).where(UserProfile.user_id == uid)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


# ── Insights ──────────────────────────────────────────────────────────────────

insights_router = APIRouter(prefix="/insights", tags=["insights"])


@insights_router.get("/{user_id}")
def get_insights(
    user_id: str,
    use_ai: bool = Query(True),
    db: Session = Depends(get_session),
    claude: ClaudeService = Depends(get_claude_service),
):
    """
    Get AI-powered spending insights for the current billing period.
    Set use_ai=false to skip Claude (faster, for testing).
    """
    uid = _uid(user_id)
    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    profile = _get_profile(uid, db)

    # Determine billing period
    start, end = analytics.get_billing_period(profile.billing_cycle_day)

    # Last period for comparison
    prev_end = start
    prev_start, _ = analytics.get_billing_period(
        profile.billing_cycle_day,
        reference_date=start - __import__('datetime').timedelta(days=1)
    )

    summary = analytics.compute_spending_summary(
        db, uid, start, end,
        vs_start=prev_start, vs_end=prev_end,
    )
    alert_list = alerts_svc.detect_alerts(db, uid, summary)
    health_score = analytics.compute_health_score(summary, alert_list)

    recommendations = []
    credit_tip = "Paying your full balance monthly avoids interest and builds strong payment history."

    if use_ai:
        try:
            ai_result = claude.generate_insights(summary, alert_list, profile)
            recommendations = ai_result.get("recommendations", [])
            credit_tip = ai_result.get("credit_education_tip", credit_tip)
            ai_score = ai_result.get("health_score")
            if ai_score:
                health_score = int(ai_score)
        except Exception as e:
            logger.error(f"Claude insights generation failed: {e}")

    if not recommendations:
        recommendations = [
            "Review your top spending categories this period.",
            "Keep credit utilization below 30% for the best score impact.",
            "Set a weekly discretionary budget to reduce end-of-month surprises.",
        ]

    return {
        "user_id": uid,
        "user_name": profile.name,
        "summary": summary,
        "alerts": alert_list,
        "health_score": health_score,
        "recommendations": recommendations,
        "credit_education_tip": credit_tip,
    }


# ── Reports ───────────────────────────────────────────────────────────────────

reports_router = APIRouter(prefix="/reports", tags=["reports"])


@reports_router.get("/{user_id}/monthly")
def get_monthly_report(
    user_id: str,
    month: Optional[str] = Query(None, description="YYYY-MM. Defaults to most recent."),
    use_ai: bool = Query(True),
    db: Session = Depends(get_session),
    claude: ClaudeService = Depends(get_claude_service),
):
    """
    Generate a full monthly financial health report.
    Includes AI narrative, action items, health score, and available months.
    """
    uid = _uid(user_id)
    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    profile = _get_profile(uid, db)
    available_months = analytics.get_available_months(db, uid)

    if not available_months:
        raise HTTPException(status_code=404, detail="No transaction data found")

    target_month = month or available_months[0]
    if target_month not in available_months:
        raise HTTPException(status_code=404, detail=f"No data for month {target_month}")

    start, end = analytics.get_month_range(target_month)

    # Previous month for comparison
    prev_month_idx = available_months.index(target_month)
    prev_start = prev_end = None
    if prev_month_idx + 1 < len(available_months):
        prev_start, prev_end = analytics.get_month_range(
            available_months[prev_month_idx + 1]
        )

    summary = analytics.compute_spending_summary(
        db, uid, start, end, vs_start=prev_start, vs_end=prev_end
    )
    alert_list = alerts_svc.detect_alerts(db, uid, summary)
    health_score = analytics.compute_health_score(summary, alert_list)

    top_cats = summary.get("top_categories", [])
    biggest_category = top_cats[0]["category"] if top_cats else "unknown"

    spending_data = {
        **{k: str(v) for k, v in summary.items() if k != "_raw_transactions"},
        "health_score": health_score,
        "biggest_category": biggest_category,
    }

    ai_narrative = f"Here's your {target_month} summary — {summary['transaction_count']} transactions."
    action_items = [
        "Review your top spending categories",
        "Check your credit utilization",
        "Set goals for next month",
    ]
    badges_earned = []
    biggest_risk = None

    if use_ai:
        try:
            ai_result = claude.generate_monthly_report(
                profile.name, target_month, spending_data, profile
            )
            ai_narrative = ai_result.get("ai_narrative", ai_narrative)
            action_items = ai_result.get("action_items", action_items)
            badges_earned = ai_result.get("badges_earned", [])
            biggest_risk = ai_result.get("biggest_risk")
        except Exception as e:
            logger.error(f"Claude monthly report generation failed: {e}")

    return {
        "user_id": uid,
        "user_name": profile.name,
        "month": target_month,
        "health_score": health_score,
        "summary": summary,
        "alerts": alert_list,
        "biggest_category": biggest_category,
        "ai_narrative": ai_narrative,
        "action_items": action_items,
        "badges_earned": badges_earned,
        "biggest_risk": biggest_risk,
        "available_months": available_months,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GOALS ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from models.schemas import GoalCreate, GoalUpdate, GoalProgressCreate, GoalListResponse, GoalResponse
from services import goals as goals_svc
from uuid import uuid4

goals_router = APIRouter(prefix="/goals", tags=["goals"])


@goals_router.get("/", response_model=GoalListResponse)
def list_goals(
    user_id: str = Query(...),
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    all_goals = goals_svc.get_all_goals(db, uid)
    active_count = sum(1 for g in all_goals if g.status == "active")

    return GoalListResponse(
        goals=[GoalResponse(**goals_svc.goal_to_response_dict(g)) for g in all_goals],
        active_count=active_count,
    )


@goals_router.post("/", response_model=GoalResponse, status_code=201)
def create_goal(
    user_id: str = Query(...),
    body: GoalCreate = ...,
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")
    goal = goals_svc.create_goal(db, uid, body)
    return GoalResponse(**goals_svc.goal_to_response_dict(goal))


@goals_router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: str,
    user_id: str = Query(...),
    body: GoalUpdate = ...,
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    try:
        gid = UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")
    goal = goals_svc.update_goal(db, gid, uid, body)
    return GoalResponse(**goals_svc.goal_to_response_dict(goal))


@goals_router.post("/{goal_id}/progress", response_model=GoalResponse)
def add_goal_progress(
    goal_id: str,
    user_id: str = Query(...),
    body: GoalProgressCreate = ...,
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    try:
        gid = UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")
    goal = goals_svc.add_progress(db, gid, uid, body)
    return GoalResponse(**goals_svc.goal_to_response_dict(goal))


@goals_router.delete("/{goal_id}", response_model=MessageResponse)
def delete_goal(
    goal_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    try:
        gid = UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")
    goals_svc.delete_goal(db, gid, uid)
    return MessageResponse(message="Goal deleted")


# ─────────────────────────────────────────────────────────────────────────────
# NUDGES ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from models.orm import Nudge
from models.schemas import NudgeResponse, NudgeFeedbackUpdate

nudges_router = APIRouter(prefix="/nudges", tags=["nudges"])


@nudges_router.get("/", response_model=list[NudgeResponse])
def get_nudges(
    user_id: str = Query(...),
    unseen_only: bool = Query(True),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_session),
):
    """
    Get queued nudges for a user.
    By default returns only unseen nudges (shown_at is null).
    Marks returned nudges as shown.
    """
    uid = _uid(user_id)
    query = select(Nudge).where(Nudge.user_id == uid)
    if unseen_only:
        query = query.where(Nudge.shown_at.is_(None))

    nudges = db.exec(
        query.order_by(Nudge.created_at.desc()).limit(limit)
    ).all()

    # Mark as shown
    now = datetime.utcnow()
    for nudge in nudges:
        if not nudge.shown_at:
            nudge.shown_at = now
            db.add(nudge)
    db.commit()

    return [NudgeResponse.model_validate(n) for n in nudges]


@nudges_router.patch("/{nudge_id}/dismiss", response_model=MessageResponse)
def dismiss_nudge(
    nudge_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    try:
        nid = UUID(nudge_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid nudge_id")

    nudge = db.exec(
        select(Nudge).where(Nudge.id == nid, Nudge.user_id == uid)
    ).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")

    nudge.dismissed_at = datetime.utcnow()
    db.add(nudge)
    db.commit()
    return MessageResponse(message="Nudge dismissed")


@nudges_router.patch("/{nudge_id}/feedback", response_model=MessageResponse)
def nudge_feedback(
    nudge_id: str,
    user_id: str = Query(...),
    body: NudgeFeedbackUpdate = ...,
    db: Session = Depends(get_session),
):
    uid = _uid(user_id)
    try:
        nid = UUID(nudge_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid nudge_id")

    nudge = db.exec(
        select(Nudge).where(Nudge.id == nid, Nudge.user_id == uid)
    ).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")

    nudge.feedback = body.feedback.value
    nudge.feedback_at = datetime.utcnow()
    db.add(nudge)
    db.commit()
    return MessageResponse(message="Feedback recorded")


# ─────────────────────────────────────────────────────────────────────────────
# ACHIEVEMENTS ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from services import achievements as ach_svc

achievements_router = APIRouter(prefix="/achievements", tags=["achievements"])


@achievements_router.get("/")
def get_achievements(
    user_id: str = Query(...),
    db: Session = Depends(get_session),
):
    """Return full achievement catalog with earned/unearned status for this user."""
    uid = _uid(user_id)
    achievements = ach_svc.get_user_achievements_with_catalog(db, uid)
    total_points = ach_svc.get_total_points(db, uid)
    earned_count = sum(1 for a in achievements if a["unlocked"])

    return {
        "achievements": achievements,
        "total_points": total_points,
        "earned_count": earned_count,
        "total_count": len(achievements),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DEMO CONTROL PANEL ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from models.schemas import DemoLoadPersona, DemoTriggerEvent
from ingestion.ingester import TransactionIngester
from sqlmodel import delete

demo_router = APIRouter(prefix="/demo", tags=["demo"])


@demo_router.post("/load-persona")
def load_persona(
    body: DemoLoadPersona,
    db: Session = Depends(get_session),
):
    """
    Load a pre-configured demo persona's transaction history.
    Clears existing transactions and re-ingests the persona's data.
    Used by the demo control panel.
    """
    from models.orm import Transaction as TxnModel
    uid = body.user_id

    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    # Clear existing transactions for clean demo state
    db.exec(delete(TxnModel).where(TxnModel.user_id == uid))
    db.commit()

    # Re-ingest with selected persona
    ingester = TransactionIngester(db)
    result = ingester.ingest(user_id=uid, persona_key=body.persona_key)

    return {
        "message": f"Loaded persona '{body.persona_key}'",
        "transactions_loaded": result["inserted"],
    }


@demo_router.post("/reset/{user_id}")
def reset_user_data(
    user_id: str,
    persona_key: str = Query("alex"),
    db: Session = Depends(get_session),
):
    """
    Reset all transaction data for a user and reload with fresh persona data.
    Preserves the user's profile. Used between demos.
    """
    from models.orm import (
        Transaction as TxnModel, Nudge as NudgeModel,
        UserAchievement, GoalProgressSnapshot, Goal,
        UserEducationCard,
    )
    uid = _uid(user_id)

    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    # Clear all generated/computed data — keep profile and goals structure
    db.exec(delete(UserEducationCard).where(UserEducationCard.user_id == uid))
    db.exec(delete(NudgeModel).where(NudgeModel.user_id == uid))
    db.exec(delete(UserAchievement).where(UserAchievement.user_id == uid))

    goal_ids = [
        g.id for g in db.exec(select(Goal).where(Goal.user_id == uid)).all()
    ]
    if goal_ids:
        db.exec(delete(GoalProgressSnapshot).where(
            GoalProgressSnapshot.goal_id.in_(goal_ids)
        ))

    db.exec(delete(TxnModel).where(TxnModel.user_id == uid))
    db.commit()

    # Reload fresh transaction data
    ingester = TransactionIngester(db)
    result = ingester.ingest(user_id=uid, persona_key=persona_key)

    return {
        "message": f"Reset complete — loaded persona '{persona_key}'",
        "transactions_loaded": result["inserted"],
    }


@demo_router.get("/personas")
def get_personas():
    """Return available demo personas and their descriptions."""
    from ingestion.synthetic import SyntheticAdapter
    adapter = SyntheticAdapter()
    return {"personas": adapter.get_persona_summary()}


@demo_router.post("/spike-category")
def spike_category(
    user_id: str = Query(...),
    category: str = Query(...),
    multiplier: float = Query(2.5, ge=1.5, le=5.0),
    db: Session = Depends(get_session),
):
    """
    Artificially inflate a spending category for demo purposes.
    Updates existing transactions in the category for the current month.
    """
    from models.orm import Transaction as TxnModel
    from datetime import date
    uid = _uid(user_id)

    today = date.today()
    month_start = today.replace(day=1)

    txns = db.exec(
        select(TxnModel).where(
            TxnModel.user_id == uid,
            TxnModel.raw_category == category,
            TxnModel.date >= month_start,
        )
    ).all()

    if not txns:
        raise HTTPException(
            status_code=404,
            detail=f"No '{category}' transactions found this month"
        )

    from decimal import Decimal
    for txn in txns:
        txn.amount = (txn.amount * Decimal(str(multiplier))).quantize(Decimal("0.01"))
        db.add(txn)

    db.commit()
    return {
        "message": f"Spiked {len(txns)} '{category}' transactions by {multiplier}x",
        "transactions_affected": len(txns),
    }


@demo_router.post("/trigger-education-card")
def trigger_education_card(
    user_id: str = Query(...),
    trigger_key: str = Query(...),
    db: Session = Depends(get_session),
):
    """
    Manually fire an education card trigger for demo purposes.
    Generates a Claude-powered card and queues it for the user.

    Available trigger_keys:
    - utilization_over_50
    - utilization_over_70
    - first_goal_created
    - goal_halfway
    - goal_completed
    - first_full_balance_month
    - carrying_balance_detected
    - dining_spike
    - subscription_count_high
    - income_overspend
    - stress_level_high
    - first_month_complete
    """
    from services.education import create_education_card_for_user
    from services.claude_service import ClaudeService
    from models.orm import UserProfile
    from sqlmodel import select as sql_select

    uid = _uid(user_id)

    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.exec(
        sql_select(UserProfile).where(UserProfile.user_id == uid)
    ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    claude = ClaudeService()

    card = create_education_card_for_user(
        session=db,
        user_id=uid,
        trigger_key=trigger_key,
        profile=profile,
        summary={"total_spend": 800, "utilization_rate": 67, "top_categories": []},
        context={"stress_level": profile.stress_level},
        claude_service=claude,
    )

    if not card:
        raise HTTPException(
            status_code=400,
            detail=f"Could not generate card — trigger_key '{trigger_key}' may not exist or card already received"
        )

    return {
        "message": f"Education card triggered: {trigger_key}",
        "card_id": str(card.id),
        "title": card.title,
    }