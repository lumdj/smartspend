"""
SmartSpend Health Score History

Computes health scores retroactively for each month with transaction data.
No new storage needed — derives everything from existing transactions.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from database import get_session
from models.orm import User, UserProfile
from services.analytics import (
    compute_spending_summary,
    compute_health_score,
    get_available_months,
    get_month_range,
)
from services.alerts import detect_alerts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health-history", tags=["analytics"])


def _uid(user_id: str) -> UUID:
    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")


@router.get("/")
def get_health_history(
    user_id: str = Query(...),
    months: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_session),
):
    """
    Compute health scores for the last N months retroactively.
    Returns a time series suitable for a line chart.
    """
    uid = _uid(user_id)

    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.exec(
        select(UserProfile).where(UserProfile.user_id == uid)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    available = get_available_months(db, uid)
    if not available:
        return {"history": [], "trend": "neutral", "current_score": 0}

    # Take the most recent N months
    target_months = available[:months]
    target_months.reverse()  # Oldest first for chart ordering

    history = []
    for month_str in target_months:
        try:
            start, end = get_month_range(month_str)
            summary = compute_spending_summary(db, uid, start, end)
            alerts = detect_alerts(db, uid, summary)
            score = compute_health_score(summary, alerts)

            history.append({
                "month": month_str,
                "label": _format_month_label(month_str),
                "score": score,
                "total_spend": float(summary.get("total_spend", 0)),
                "utilization": summary.get("utilization_rate", 0),
            })
        except Exception as e:
            logger.warning(f"Could not compute score for {month_str}: {e}")
            continue

    if not history:
        return {"history": [], "trend": "neutral", "current_score": 0}

    # Compute trend — compare last month to first month
    trend = "neutral"
    if len(history) >= 2:
        delta = history[-1]["score"] - history[0]["score"]
        if delta >= 5:
            trend = "improving"
        elif delta <= -5:
            trend = "declining"

    current_score = history[-1]["score"] if history else 0
    avg_score = round(sum(h["score"] for h in history) / len(history))
    best_month = max(history, key=lambda h: h["score"])
    worst_month = min(history, key=lambda h: h["score"])

    return {
        "history": history,
        "trend": trend,
        "current_score": current_score,
        "avg_score": avg_score,
        "best_month": best_month["label"],
        "worst_month": worst_month["label"],
        "delta": history[-1]["score"] - history[0]["score"] if len(history) >= 2 else 0,
    }


def _format_month_label(month_str: str) -> str:
    """Convert YYYY-MM to short label like 'Jan' or 'Mar'."""
    months = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
    }
    parts = month_str.split("-")
    if len(parts) == 2:
        return months.get(parts[1], month_str)
    return month_str
