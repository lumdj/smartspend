"""
SmartSpend Goals Service

Business logic for goal management:
- Enforces 3 active goal cap
- Tracks progress (manual, auto-category, recap deposit)
- Computes progress percentages
- Handles goal completion flow
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlmodel import Session, select

from models.orm import Goal, GoalProgressSnapshot, Nudge
from models.schemas import GoalCreate, GoalUpdate, GoalProgressCreate

logger = logging.getLogger(__name__)

MAX_ACTIVE_GOALS = 3


# ── Queries ───────────────────────────────────────────────────────────────────

def get_active_goals(session: Session, user_id: UUID) -> list[Goal]:
    return session.exec(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.status == "active",
        ).order_by(Goal.created_at.asc())
    ).all()


def get_all_goals(session: Session, user_id: UUID) -> list[Goal]:
    return session.exec(
        select(Goal).where(
            Goal.user_id == user_id
        ).order_by(Goal.created_at.desc())
    ).all()


def get_goal_or_404(session: Session, goal_id: UUID, user_id: UUID) -> Goal:
    goal = session.exec(
        select(Goal).where(
            Goal.id == goal_id,
            Goal.user_id == user_id,
        )
    ).first()
    if not goal:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )
    return goal


# ── Goal CRUD ─────────────────────────────────────────────────────────────────

def create_goal(
    session: Session,
    user_id: UUID,
    data: GoalCreate,
) -> Goal:
    """
    Create a new goal, enforcing the 3 active goal cap.
    Raises HTTPException if cap is already reached.
    """
    active = get_active_goals(session, user_id)
    if len(active) >= MAX_ACTIVE_GOALS:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"You already have {MAX_ACTIVE_GOALS} active goals. "
                f"Complete, pause, or remove one before adding another."
            ),
        )

    goal = Goal(
        id=uuid4(),
        user_id=user_id,
        name=data.name,
        goal_type=data.goal_type.value,
        target_amount=data.target_amount,
        current_amount=Decimal("0.00"),
        target_date=data.target_date,
        status="active",
        linked_category=data.linked_category,
        icon=data.icon or "🎯",
        photo_url=data.photo_url,
        reason=data.reason,
        auto_deposit_amount=data.auto_deposit_amount,
        auto_deposit_enabled=data.auto_deposit_enabled,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)

    logger.info(f"Created goal '{goal.name}' for user {user_id}")
    return goal


def update_goal(
    session: Session,
    goal_id: UUID,
    user_id: UUID,
    data: GoalUpdate,
) -> Goal:
    """Partial update — only provided fields are changed."""
    goal = get_goal_or_404(session, goal_id, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(goal, field, value)

    goal.updated_at = datetime.utcnow()

    # If status just changed to completed, record the completion
    if update_data.get("status") == "completed":
        _handle_goal_completion(session, goal)

    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def delete_goal(session: Session, goal_id: UUID, user_id: UUID) -> None:
    """Hard delete a goal and all its progress snapshots."""
    goal = get_goal_or_404(session, goal_id, user_id)

    # Delete snapshots first
    from sqlmodel import delete
    session.exec(
        delete(GoalProgressSnapshot).where(
            GoalProgressSnapshot.goal_id == goal_id
        )
    )
    session.delete(goal)
    session.commit()
    logger.info(f"Deleted goal {goal_id} for user {user_id}")


# ── Progress Tracking ─────────────────────────────────────────────────────────

def add_progress(
    session: Session,
    goal_id: UUID,
    user_id: UUID,
    data: GoalProgressCreate,
) -> Goal:
    """
    Record a progress contribution and update goal.current_amount.
    Automatically marks goal complete if target is reached.
    """
    goal = get_goal_or_404(session, goal_id, user_id)

    if goal.status not in ("active", "paused"):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add progress to a {goal.status} goal",
        )

    recorded_date = data.recorded_date or date.today()
    new_amount = goal.current_amount + data.amount

    # Record the snapshot
    snapshot = GoalProgressSnapshot(
        id=uuid4(),
        goal_id=goal_id,
        user_id=user_id,
        recorded_date=recorded_date,
        amount_saved=new_amount,
        delta=data.amount,
        source=data.source.value,
        notes=data.notes,
        created_at=datetime.utcnow(),
    )
    session.add(snapshot)

    # Update current amount
    goal.current_amount = new_amount
    goal.updated_at = datetime.utcnow()

    # Auto-complete if target reached
    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
        _handle_goal_completion(session, goal)
        logger.info(f"Goal '{goal.name}' completed for user {user_id}")

    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def get_progress_history(
    session: Session,
    goal_id: UUID,
    user_id: UUID,
) -> list[GoalProgressSnapshot]:
    """Return all progress snapshots for a goal, oldest first."""
    # Verify ownership
    get_goal_or_404(session, goal_id, user_id)

    return session.exec(
        select(GoalProgressSnapshot).where(
            GoalProgressSnapshot.goal_id == goal_id
        ).order_by(GoalProgressSnapshot.recorded_date.asc())
    ).all()


# ── Auto-Progress ─────────────────────────────────────────────────────────────

def apply_category_auto_progress(
    session: Session,
    user_id: UUID,
    category: str,
    savings_amount: Decimal,
    reference_date: date,
) -> list[Goal]:
    """
    Apply automatic progress to goals linked to a spending category.
    Called by the analytics pipeline when category spend is below average.

    Returns list of goals that were updated.
    """
    linked_goals = session.exec(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.status == "active",
            Goal.linked_category == category,
        )
    ).all()

    updated = []
    for goal in linked_goals:
        snapshot = GoalProgressSnapshot(
            id=uuid4(),
            goal_id=goal.id,
            user_id=user_id,
            recorded_date=reference_date,
            amount_saved=goal.current_amount + savings_amount,
            delta=savings_amount,
            source="auto_category",
            notes=f"Auto: saved ${savings_amount:.2f} in {category}",
            created_at=datetime.utcnow(),
        )
        session.add(snapshot)
        goal.current_amount += savings_amount
        goal.updated_at = datetime.utcnow()

        if goal.current_amount >= goal.target_amount:
            goal.status = "completed"
            _handle_goal_completion(session, goal)

        session.add(goal)
        updated.append(goal)

    if updated:
        session.commit()

    return updated


# ── Helpers ───────────────────────────────────────────────────────────────────

def goal_to_response_dict(goal: Goal) -> dict:
    """Convert ORM Goal to response dict with computed progress_pct."""
    progress_pct = 0.0
    if goal.target_amount > 0:
        progress_pct = float(
            min(goal.current_amount / goal.target_amount * 100, Decimal("100"))
        )

    return {
        "id": goal.id,
        "user_id": goal.user_id,
        "name": goal.name,
        "goal_type": goal.goal_type,
        "target_amount": goal.target_amount,
        "current_amount": goal.current_amount,
        "target_date": goal.target_date,
        "status": goal.status,
        "linked_category": goal.linked_category,
        "icon": goal.icon,
        "reason": goal.reason,
        "auto_deposit_enabled": goal.auto_deposit_enabled,
        "progress_pct": round(progress_pct, 1),
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
    }


def _handle_goal_completion(session: Session, goal: Goal) -> None:
    """
    Queue a completion nudge when a goal is finished.
    The nudge surfaces the celebration screen on next app open.
    """
    nudge = Nudge(
        id=uuid4(),
        user_id=goal.user_id,
        nudge_type="goal_progress",
        message=(
            f"You did it! 🎉 '{goal.name}' is complete. "
            f"That's a real win — take a moment to appreciate it before setting your next goal."
        ),
        related_goal_id=goal.id,
        created_at=datetime.utcnow(),
    )
    session.add(nudge)
    logger.info(f"Queued completion nudge for goal '{goal.name}'")
