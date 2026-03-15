"""
SmartSpend Alerts Service

Rule-based alert detection. Runs after analytics computation
and before Claude enrichment. Produces structured alert dicts
that Claude uses for context when generating insights.

Rules are intentionally conservative — we'd rather surface
a few meaningful alerts than flood the user with noise.
"""

import logging
from decimal import Decimal
from datetime import date
from uuid import UUID
from sqlmodel import Session

from models.orm import UserProfile
from services.analytics import (
    compute_spending_summary,
    get_billing_period,
    get_category_weekly_trend,
    _parse_income_midpoint,
)

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
UTILIZATION_WARNING = 50      # % — triggers warning
UTILIZATION_CRITICAL = 70     # % — triggers critical
DINING_PCT_WARNING = 25       # % of income
DISCRETIONARY_PCT_WARNING = 55  # % of total spend
INCOME_RATIO_WARNING = 85     # % of income spent
INCOME_RATIO_CRITICAL = 100   # % of income spent
SUBSCRIPTION_SPIKE_COUNT = 4  # Number of subscription txns that triggers alert


def detect_alerts(
    session: Session,
    user_id: UUID,
    summary: dict,
) -> list[dict]:
    """
    Run all alert rules against a spending summary.

    Args:
        session: DB session (for profile lookup)
        user_id: User to check
        summary: Pre-computed spending summary from analytics service

    Returns:
        List of alert dicts, ordered by severity (critical first).
        Each dict matches the AlertResponse schema.
    """
    profile = session.get(UserProfile, _get_profile_id(session, user_id))
    if not profile:
        return []

    alerts = []
    income = _parse_income_midpoint(profile.monthly_income_range)

    # ── Rule 1: Credit utilization ────────────────────────────────────────
    util = summary.get("utilization_rate", 0)
    if util >= UTILIZATION_CRITICAL:
        alerts.append({
            "alert_type": "near_limit",
            "severity": "critical",
            "category": None,
            "message": (
                f"Your credit utilization is {util:.0f}% — "
                f"anything above 70% can drop your score by 50+ points. "
                f"Try to pay down your balance before your statement closes."
            ),
            "amount": float(summary.get("total_spend", 0)),
            "threshold": float(profile.credit_limit * Decimal("0.70")),
        })
    elif util >= UTILIZATION_WARNING:
        alerts.append({
            "alert_type": "near_limit",
            "severity": "warning",
            "category": None,
            "message": (
                f"Credit utilization is at {util:.0f}%. "
                f"Staying under 30% gives you the best score impact — "
                f"you're currently in the caution zone."
            ),
            "amount": float(summary.get("total_spend", 0)),
            "threshold": float(profile.credit_limit * Decimal("0.30")),
        })

    # ── Rule 2: Spending exceeds income ───────────────────────────────────
    income_ratio = summary.get("income_spend_ratio", 0)
    if income_ratio >= INCOME_RATIO_CRITICAL:
        alerts.append({
            "alert_type": "high_spend",
            "severity": "critical",
            "category": None,
            "message": (
                f"You've spent more than your entire monthly income this period. "
                f"If you're carrying a balance, interest charges are actively "
                f"working against your financial progress."
            ),
            "amount": float(summary.get("total_spend", 0)),
            "threshold": float(income),
        })
    elif income_ratio >= INCOME_RATIO_WARNING:
        alerts.append({
            "alert_type": "high_spend",
            "severity": "warning",
            "category": None,
            "message": (
                f"You've used {income_ratio:.0f}% of your monthly income this period. "
                f"That leaves very little buffer for unexpected expenses."
            ),
            "amount": float(summary.get("total_spend", 0)),
            "threshold": float(income * Decimal("0.85")),
        })

    # ── Rule 3: Dining spike ──────────────────────────────────────────────
    dining_amount = next(
        (c["amount"] for c in summary.get("top_categories", [])
         if c["category"] == "dining"),
        0,
    )
    dining_threshold = float(income * Decimal(str(DINING_PCT_WARNING)) / 100)
    if income > 0 and dining_amount > dining_threshold:
        dining_pct = round(dining_amount / float(income) * 100, 1)
        alerts.append({
            "alert_type": "category_spike",
            "severity": "warning",
            "category": "dining",
            "message": (
                f"Dining is ${dining_amount:.0f} this period — "
                f"{dining_pct}% of your income. "
                f"Small daily purchases add up faster than any single big expense."
            ),
            "amount": dining_amount,
            "threshold": dining_threshold,
        })

    # ── Rule 4: High discretionary ratio ─────────────────────────────────
    total = float(summary.get("total_spend", 1))
    disc = float(summary.get("discretionary_spend", 0))
    disc_pct = round(disc / total * 100, 1) if total > 0 else 0
    if disc_pct >= DISCRETIONARY_PCT_WARNING:
        alerts.append({
            "alert_type": "high_spend",
            "severity": "warning",
            "category": "discretionary",
            "message": (
                f"{disc_pct:.0f}% of your spending this period was discretionary. "
                f"The 50/30/20 rule suggests keeping wants under 30%."
            ),
            "amount": disc,
            "threshold": total * 0.30,
        })

    # ── Rule 5: Subscription count ────────────────────────────────────────
    sub_txns = [
        t for t in summary.get("_raw_transactions", [])
        if t.get("raw_category") == "subscriptions"
    ]
    if len(sub_txns) >= SUBSCRIPTION_SPIKE_COUNT:
        sub_total = sum(t.get("amount", 0) for t in sub_txns)
        alerts.append({
            "alert_type": "category_spike",
            "severity": "info",
            "category": "subscriptions",
            "message": (
                f"You have {len(sub_txns)} subscription charges totaling "
                f"${sub_total:.0f} this period. "
                f"Worth auditing — the average person has 4+ they've forgotten about."
            ),
            "amount": sub_total,
            "threshold": 0,
        })

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 3))

    return alerts


def _get_profile_id(session: Session, user_id: UUID):
    """Helper to fetch UserProfile by user_id since PK is profile.id."""
    from sqlmodel import select
    from models.orm import UserProfile
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).first()
    return profile.id if profile else None
