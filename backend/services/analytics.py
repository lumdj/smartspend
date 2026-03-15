"""
SmartSpend Analytics Service

Pure computation layer — no AI, no HTTP calls, no side effects.
Takes data from the DB and returns structured summaries.

All methods accept a SQLModel Session and user_id.
Nothing here modifies the database.

Security notes:
- All monetary arithmetic uses Decimal, never float
- Division is guarded against ZeroDivisionError throughout
- Date ranges are always computed server-side, never trusted from client
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from models.orm import Transaction, UserProfile, MerchantOverride

logger = logging.getLogger(__name__)

# ── Billing Period Helpers ────────────────────────────────────────────────────

def get_billing_period(
    billing_cycle_day: Optional[int],
    reference_date: Optional[date] = None,
) -> tuple[date, date]:
    """
    Returns (period_start, period_end) for the current billing period.

    If billing_cycle_day is set, uses the billing cycle window.
    If not set, falls back to the current calendar month.

    Args:
        billing_cycle_day: Day of month the statement closes (1-28), or None
        reference_date: Date to compute period from. Defaults to today.
    """
    today = reference_date or date.today()

    if not billing_cycle_day:
        # Calendar month fallback
        period_start = today.replace(day=1)
        # Last day of current month
        if today.month == 12:
            period_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            period_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return period_start, period_end

    # Billing cycle window
    if today.day >= billing_cycle_day:
        # We're past the cycle day — current cycle started this month
        period_start = today.replace(day=billing_cycle_day)
    else:
        # We're before the cycle day — current cycle started last month
        if today.month == 1:
            period_start = today.replace(year=today.year - 1, month=12, day=billing_cycle_day)
        else:
            period_start = today.replace(month=today.month - 1, day=billing_cycle_day)

    # Period ends the day before the next cycle closes
    if period_start.month == 12:
        next_close = period_start.replace(year=period_start.year + 1, month=1, day=billing_cycle_day)
    else:
        next_close = period_start.replace(month=period_start.month + 1, day=billing_cycle_day)

    period_end = next_close - timedelta(days=1)
    return period_start, period_end


def get_month_range(month_str: str) -> tuple[date, date]:
    """
    Convert a YYYY-MM string to (first_day, last_day) of that month.
    """
    year, month = int(month_str[:4]), int(month_str[5:7])
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


# ── Core Analytics ────────────────────────────────────────────────────────────

def get_transactions_for_period(
    session: Session,
    user_id: UUID,
    start: date,
    end: date,
) -> list[Transaction]:
    """Fetch all transactions for a user within a date range."""
    return session.exec(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.date >= start,
            Transaction.date <= end,
        ).order_by(Transaction.date.desc())
    ).all()


def compute_spending_summary(
    session: Session,
    user_id: UUID,
    start: date,
    end: date,
    vs_start: Optional[date] = None,
    vs_end: Optional[date] = None,
) -> dict:
    """
    Compute a full spending breakdown for a period.

    Args:
        session: DB session
        user_id: User to compute for
        start/end: The period to summarize
        vs_start/vs_end: Optional comparison period for deltas

    Returns:
        Dict matching the SpendingSummary schema
    """
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).first()

    if not profile:
        raise ValueError(f"No profile found for user {user_id}")

    txns = get_transactions_for_period(session, user_id, start, end)

    # Load merchant overrides for category correction
    overrides = {
        o.merchant_name.lower(): o.preferred_category
        for o in session.exec(
            select(MerchantOverride).where(MerchantOverride.user_id == user_id)
        ).all()
    }

    total = Decimal("0")
    essential = Decimal("0")
    semi = Decimal("0")
    discretionary = Decimal("0")
    by_category: dict[str, Decimal] = defaultdict(Decimal)

    for txn in txns:
        amount = txn.amount
        total += amount

        # Apply merchant override to category if exists
        category = overrides.get(txn.merchant.lower(), txn.raw_category)

        # Re-derive priority if category was overridden
        priority = _category_to_priority(category, txn.priority)

        if priority == "essential":
            essential += amount
        elif priority == "semi-essential":
            semi += amount
        else:
            discretionary += amount

        by_category[category] += amount

    # Top 5 categories by spend
    top_categories = sorted(
        [
            {"category": cat, "amount": float(amt.quantize(Decimal("0.01")))}
            for cat, amt in by_category.items()
        ],
        key=lambda x: x["amount"],
        reverse=True,
    )[:5]

    credit_limit = profile.credit_limit or Decimal("1")
    utilization = float(
        (total / credit_limit * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    ) if credit_limit > 0 else 0.0

    # Parse monthly income range to a midpoint for ratio computation
    income = _parse_income_midpoint(profile.monthly_income_range)
    income_ratio = float(
        (total / income * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    ) if income > 0 else 0.0

    summary = {
        "user_id": user_id,
        "period_start": start,
        "period_end": end,
        "total_spend": total,
        "essential_spend": essential,
        "semi_essential_spend": semi,
        "discretionary_spend": discretionary,
        "utilization_rate": utilization,
        "income_spend_ratio": income_ratio,
        "transaction_count": len(txns),
        "top_categories": top_categories,
        "vs_last_period": None,
    }

    # Compute period-over-period deltas if comparison range provided
    if vs_start and vs_end:
        prev_txns = get_transactions_for_period(session, user_id, vs_start, vs_end)
        prev_total = sum(t.amount for t in prev_txns)
        if prev_total > 0:
            delta_pct = float(
                ((total - prev_total) / prev_total * 100).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
            summary["vs_last_period"] = {
                "total_spend": float(prev_total),
                "delta_amount": float(total - prev_total),
                "delta_pct": delta_pct,
                "direction": "up" if total > prev_total else "down",
            }

    return summary


def compute_health_score(
    summary: dict,
    alerts: list[dict],
) -> int:
    """
    Compute a 0-100 financial health score from spending summary and alerts.

    Scoring breakdown:
    - Utilization (40 pts): under 30% = full points, scales down to 0 at 80%+
    - Discretionary ratio (30 pts): under 40% = full points, scales to 0 at 70%+
    - Income ratio (30 pts): under 60% = full points, scales to 0 at 100%+

    Penalty: -5 per critical alert, -2 per warning alert
    """
    score = 100

    # Utilization score (40 points)
    util = summary.get("utilization_rate", 0)
    if util <= 30:
        util_score = 40
    elif util <= 50:
        util_score = int(40 * (1 - (util - 30) / 20 * 0.5))
    elif util <= 70:
        util_score = int(40 * 0.5 * (1 - (util - 50) / 20 * 0.75))
    else:
        util_score = 0
    score = util_score

    # Discretionary ratio score (30 points)
    total = summary.get("total_spend", Decimal("1"))
    disc = summary.get("discretionary_spend", Decimal("0"))
    disc_ratio = float(disc / total * 100) if total > 0 else 0
    if disc_ratio <= 40:
        disc_score = 30
    elif disc_ratio <= 55:
        disc_score = int(30 * (1 - (disc_ratio - 40) / 15 * 0.5))
    elif disc_ratio <= 70:
        disc_score = int(30 * 0.5 * (1 - (disc_ratio - 55) / 15))
    else:
        disc_score = 0
    score += disc_score

    # Income ratio score (30 points)
    income_ratio = summary.get("income_spend_ratio", 0)
    if income_ratio <= 60:
        income_score = 30
    elif income_ratio <= 80:
        income_score = int(30 * (1 - (income_ratio - 60) / 20 * 0.6))
    elif income_ratio <= 100:
        income_score = int(30 * 0.4 * (1 - (income_ratio - 80) / 20))
    else:
        income_score = 0
    score += income_score

    # Alert penalties
    for alert in alerts:
        if alert.get("severity") == "critical":
            score -= 5
        elif alert.get("severity") == "warning":
            score -= 2

    return max(0, min(100, score))


def get_available_months(session: Session, user_id: UUID) -> list[str]:
    """
    Return sorted list of YYYY-MM strings for months with transaction data.
    Newest first. Used to populate month selector in reports.
    """
    txns = session.exec(
        select(Transaction.date).where(
            Transaction.user_id == user_id
        )
    ).all()

    months = sorted(
        set(d.strftime("%Y-%m") for d in txns),
        reverse=True,
    )
    return months


def get_category_weekly_trend(
    session: Session,
    user_id: UUID,
    category: str,
    weeks: int = 4,
) -> list[dict]:
    """
    Return weekly spend totals for a category over the past N weeks.
    Used for the dining reduction achievement trigger.
    """
    today = date.today()
    result = []

    for i in range(weeks):
        week_end = today - timedelta(days=7 * i)
        week_start = week_end - timedelta(days=6)

        txns = session.exec(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.raw_category == category,
                Transaction.date >= week_start,
                Transaction.date <= week_end,
            )
        ).all()

        total = sum(t.amount for t in txns)
        result.append({
            "week_start": week_start,
            "week_end": week_end,
            "total": float(total),
        })

    return result


# ── Private Helpers ───────────────────────────────────────────────────────────

def _category_to_priority(category: str, fallback: str) -> str:
    """
    Re-derive priority from category after a merchant override.
    Returns fallback if category is not in the known map.
    """
    essential_categories = {
        "groceries", "health", "transportation", "utilities", "rent", "insurance"
    }
    semi_categories = {
        "subscriptions", "fitness", "phone"
    }
    if category in essential_categories:
        return "essential"
    if category in semi_categories:
        return "semi-essential"
    if category in {"dining", "coffee", "shopping", "entertainment",
                    "nightlife", "beauty", "travel", "other"}:
        return "discretionary"
    return fallback


def _parse_income_midpoint(income_range: str) -> Decimal:
    """
    Parse a monthly income range label to a midpoint Decimal.
    e.g. '$1,000–$2,000' → Decimal('1500')
    Falls back to 1500 if unparseable.
    """
    try:
        cleaned = income_range.replace("$", "").replace(",", "").replace(" ", "")
        if "+" in cleaned:
            return Decimal(cleaned.replace("+", "").strip())
        if "Under" in income_range or "under" in income_range:
            return Decimal("250")
        separators = ["–", "-", "to"]
        for sep in separators:
            if sep in cleaned:
                parts = cleaned.split(sep)
                low = Decimal(parts[0].strip())
                high = Decimal(parts[1].strip())
                return (low + high) / Decimal("2")
    except Exception:
        pass
    return Decimal("1500")  # Reasonable fallback
