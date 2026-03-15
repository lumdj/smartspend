"""
SmartSpend Seed Script
Seeds the achievements catalog and education card triggers.
Run once after `alembic upgrade head`:
    python data/seed.py

Safe to run multiple times — uses upsert pattern.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from database import engine
from models.orm import Achievement, EducationCard
from datetime import datetime
from uuid import uuid4


ACHIEVEMENTS = [
    # ── Credit ────────────────────────────────────────────────────────────
    {
        "key": "credit_conscious",
        "name": "Credit Conscious",
        "description": "Kept credit utilization under 30% for a full month",
        "icon": "💳",
        "category": "credit",
        "trigger_condition": "utilization_under_30_for_month",
        "points": 50,
    },
    {
        "key": "danger_zone_avoided",
        "name": "Danger Zone Avoided",
        "description": "Brought utilization down from over 70% to under 50%",
        "icon": "🛡️",
        "category": "credit",
        "trigger_condition": "utilization_dropped_from_danger",
        "points": 75,
    },
    {
        "key": "debt_dodger",
        "name": "Debt Dodger",
        "description": "Paid full balance 3 months in a row",
        "icon": "🚫",
        "category": "credit",
        "trigger_condition": "full_balance_3_months",
        "points": 80,
    },
    {
        "key": "first_full_balance",
        "name": "Interest-Free",
        "description": "Paid your full balance for the first time",
        "icon": "✅",
        "category": "credit",
        "trigger_condition": "first_full_balance_month",
        "points": 30,
    },
    # ── Spending ──────────────────────────────────────────────────────────
    {
        "key": "under_budget",
        "name": "Under Budget",
        "description": "Spent less than 80% of your monthly income",
        "icon": "📉",
        "category": "spending",
        "trigger_condition": "spend_under_80pct_income",
        "points": 75,
    },
    {
        "key": "dining_detective",
        "name": "Dining Detective",
        "description": "Reduced dining spend 3 weeks in a row",
        "icon": "🍽️",
        "category": "spending",
        "trigger_condition": "dining_reduced_3_weeks",
        "points": 40,
    },
    {
        "key": "subscription_audit",
        "name": "Subscription Auditor",
        "description": "Had fewer than 3 subscription charges in a month",
        "icon": "📱",
        "category": "spending",
        "trigger_condition": "subscriptions_under_3",
        "points": 35,
    },
    # ── Goals ─────────────────────────────────────────────────────────────
    {
        "key": "first_goal",
        "name": "Dream Starter",
        "description": "Created your first financial goal",
        "icon": "🌱",
        "category": "goals",
        "trigger_condition": "first_goal_created",
        "points": 20,
    },
    {
        "key": "goal_halfway",
        "name": "Halfway There",
        "description": "Reached 50% progress on any goal",
        "icon": "⚡",
        "category": "goals",
        "trigger_condition": "goal_at_50pct",
        "points": 60,
    },
    {
        "key": "goal_crusher",
        "name": "Goal Crusher",
        "description": "Completed a financial goal",
        "icon": "🏆",
        "category": "goals",
        "trigger_condition": "goal_completed",
        "points": 150,
    },
    {
        "key": "three_goals",
        "name": "Visionary",
        "description": "Set 3 active goals at once",
        "icon": "🔭",
        "category": "goals",
        "trigger_condition": "three_active_goals",
        "points": 40,
    },
    # ── Streaks ───────────────────────────────────────────────────────────
    {
        "key": "streak_7",
        "name": "Week Warrior",
        "description": "Opened the app 7 days in a row",
        "icon": "🔥",
        "category": "streak",
        "trigger_condition": "app_open_7_days",
        "points": 30,
    },
    {
        "key": "streak_30",
        "name": "Monthly Regular",
        "description": "Opened the app 30 days in a row",
        "icon": "💫",
        "category": "streak",
        "trigger_condition": "app_open_30_days",
        "points": 100,
    },
    # ── Learning ──────────────────────────────────────────────────────────
    {
        "key": "knowledge_seeker",
        "name": "Knowledge Seeker",
        "description": "Read 5 education cards",
        "icon": "📚",
        "category": "learning",
        "trigger_condition": "education_cards_viewed_5",
        "points": 50,
    },
    {
        "key": "stress_drop",
        "name": "Smooth Operator",
        "description": "Money stress level dropped by 2+ points",
        "icon": "😌",
        "category": "learning",
        "trigger_condition": "stress_dropped_2_points",
        "points": 50,
    },
]


EDUCATION_CARDS = [
    {
        "trigger_key": "utilization_over_50",
        "trigger_condition": "Credit utilization crosses 50% in a billing cycle",
        "concept": "Credit utilization and its impact on your credit score",
    },
    {
        "trigger_key": "utilization_over_70",
        "trigger_condition": "Credit utilization crosses 70% in a billing cycle",
        "concept": "The danger zone — how high utilization damages your score and for how long",
    },
    {
        "trigger_key": "first_goal_created",
        "trigger_condition": "User creates their first financial goal",
        "concept": "The psychology of savings goals and why specificity drives results",
    },
    {
        "trigger_key": "goal_halfway",
        "trigger_condition": "Any goal reaches 50% progress",
        "concept": "Momentum and commitment consistency — why the second half is easier",
    },
    {
        "trigger_key": "goal_completed",
        "trigger_condition": "Any goal reaches 100% and is marked complete",
        "concept": "Compounding the savings habit — how to build on this win",
    },
    {
        "trigger_key": "first_full_balance_month",
        "trigger_condition": "User marks that they paid full balance for the first time",
        "concept": "What you just saved in interest — and what that compounds to over a year",
    },
    {
        "trigger_key": "carrying_balance_detected",
        "trigger_condition": "User profile indicates they do not pay full balance",
        "concept": "The minimum payment trap — real numbers on how long it takes and what it costs",
    },
    {
        "trigger_key": "dining_spike",
        "trigger_condition": "Dining spend exceeds 25% of monthly income",
        "concept": "Small purchase blindness — why frequent small transactions feel invisible",
    },
    {
        "trigger_key": "subscription_count_high",
        "trigger_condition": "4 or more subscription transactions detected in a month",
        "concept": "Subscription creep — the average person's forgotten recurring charges",
    },
    {
        "trigger_key": "income_overspend",
        "trigger_condition": "Total spend exceeds 90% of stated monthly income",
        "concept": "The buffer — why spending everything you earn is a risk even without debt",
    },
    {
        "trigger_key": "stress_level_high",
        "trigger_condition": "User reports stress level of 5 during check-in",
        "concept": "Financial anxiety and the avoidance cycle — why looking at the numbers helps",
    },
    {
        "trigger_key": "first_month_complete",
        "trigger_condition": "User completes their first full calendar month in the app",
        "concept": "How credit history length builds over time and why starting early matters",
    },
]


def seed():
    with Session(engine) as session:
        # ── Achievements ──────────────────────────────────────────────────
        print("Seeding achievements...")
        for data in ACHIEVEMENTS:
            existing = session.exec(
                select(Achievement).where(Achievement.key == data["key"])
            ).first()
            if existing:
                # Update in case fields changed
                for k, v in data.items():
                    setattr(existing, k, v)
                session.add(existing)
            else:
                session.add(Achievement(
                    id=uuid4(),
                    created_at=datetime.utcnow(),
                    **data
                ))
        session.commit()
        print(f"  ✓ {len(ACHIEVEMENTS)} achievements seeded")

        # ── Education Cards ───────────────────────────────────────────────
        print("Seeding education card triggers...")
        for data in EDUCATION_CARDS:
            existing = session.exec(
                select(EducationCard).where(EducationCard.trigger_key == data["trigger_key"])
            ).first()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                session.add(existing)
            else:
                session.add(EducationCard(
                    id=uuid4(),
                    created_at=datetime.utcnow(),
                    **data
                ))
        session.commit()
        print(f"  ✓ {len(EDUCATION_CARDS)} education card triggers seeded")

        print("\nSeed complete.")


if __name__ == "__main__":
    seed()
