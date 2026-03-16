"""
SmartSpend Education Router

GET   /education/              List user's education cards
PATCH /education/{id}/viewed   Mark a card as viewed
PATCH /education/{id}/feedback Submit helpful/not helpful feedback
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from database import get_session
from models.orm import UserEducationCard, EducationCard, User
from services.education import mark_card_viewed, submit_card_feedback
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/education", tags=["education"])


def _uid(user_id: str) -> UUID:
    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")


@router.get("/")
def list_education_cards(
    user_id: str = Query(...),
    unviewed_only: bool = Query(False),
    db: Session = Depends(get_session),
):
    """Return all education cards for a user with card metadata."""
    uid = _uid(user_id)

    query = select(UserEducationCard).where(UserEducationCard.user_id == uid)
    if unviewed_only:
        query = query.where(UserEducationCard.viewed_at.is_(None))

    user_cards = db.exec(
        query.order_by(UserEducationCard.triggered_at.desc())
    ).all()

    result = []
    for uc in user_cards:
        card_def = db.get(EducationCard, uc.card_id)
        result.append({
            "id": uc.id,
            "card_id": uc.card_id,
            "trigger_key": card_def.trigger_key if card_def else "",
            "concept": card_def.concept if card_def else "",
            "title": uc.title,
            "content": uc.content,
            "one_action": uc.one_action,
            "one_number": uc.one_number,
            "triggered_at": uc.triggered_at,
            "viewed_at": uc.viewed_at,
            "was_helpful": uc.was_helpful,
        })

    return {"cards": result, "total": len(result)}


@router.patch("/{card_id}/viewed")
def mark_viewed(
    card_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_session),
):
    """Mark an education card as viewed. Increments toward knowledge_seeker achievement."""
    uid = _uid(user_id)
    try:
        cid = UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid card_id")

    card = mark_card_viewed(db, cid, uid)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Count total viewed cards
    viewed_cards = db.exec(
        select(UserEducationCard).where(
            UserEducationCard.user_id == uid,
            UserEducationCard.viewed_at.is_not(None),
        )
    ).all()
    viewed_count = len(viewed_cards)

    achievement_unlocked = None

    # Unlock knowledge_seeker achievement at 5 cards viewed
    if viewed_count >= 5:
        from services.achievements import _unlock_achievement
        from models.orm import Achievement
        from sqlmodel import select as sql_select

        achievement = db.exec(
            sql_select(Achievement).where(Achievement.key == "knowledge_seeker")
        ).first()

        if achievement:
            unlocked = _unlock_achievement(
                session=db,
                user_id=uid,
                achievement=achievement,
                trigger_context={"education_cards_viewed": viewed_count},
            )
            if unlocked:
                db.commit()
                achievement_unlocked = {
                    "key": achievement.key,
                    "name": achievement.name,
                    "icon": achievement.icon,
                    "points": achievement.points,
                }

    return {
        "message": "Card marked as viewed",
        "viewed_count": viewed_count,
        "achievement_unlocked": achievement_unlocked,
    }


@router.patch("/{card_id}/feedback")
def card_feedback(
    card_id: str,
    user_id: str = Query(...),
    was_helpful: bool = Query(...),
    db: Session = Depends(get_session),
):
    """Submit feedback on an education card."""
    uid = _uid(user_id)
    try:
        cid = UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid card_id")

    card = submit_card_feedback(db, cid, uid, was_helpful)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return {"message": "Feedback recorded"}