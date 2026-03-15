"""
SmartSpend Transactions Router

GET  /transactions/               List transactions with filters
GET  /transactions/{id}           Single transaction
POST /transactions/ingest         Trigger ingestion for a user
POST /transactions/override       Set merchant category override
DELETE /transactions/override     Remove merchant override
"""

import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from database import get_session
from models.orm import Transaction, MerchantOverride, User
from models.schemas import (
    TransactionResponse,
    TransactionListResponse,
    MerchantOverrideCreate,
    MessageResponse,
)
from ingestion.ingester import TransactionIngester
from datetime import date, datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])

PAGE_SIZE = 50


def _validate_user(user_id: str, db: Session) -> UUID:
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    if not db.get(User, uid):
        raise HTTPException(status_code=404, detail="User not found")
    return uid


@router.get("/", response_model=TransactionListResponse)
def list_transactions(
    user_id: str = Query(...),
    month: Optional[str] = Query(None, description="YYYY-MM filter"),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_session),
):
    """
    List transactions for a user with optional filters.
    Results are paginated — 50 per page, newest first.
    """
    uid = _validate_user(user_id, db)

    query = select(Transaction).where(Transaction.user_id == uid)

    if month:
        try:
            year, mo = int(month[:4]), int(month[5:7])
            start = date(year, mo, 1)
            end = date(year, mo + 1, 1) if mo < 12 else date(year + 1, 1, 1)
            query = query.where(
                Transaction.date >= start,
                Transaction.date < end,
            )
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    if category:
        query = query.where(Transaction.raw_category == category)

    if priority:
        if priority not in ("essential", "semi-essential", "discretionary"):
            raise HTTPException(status_code=400, detail="Invalid priority value")
        query = query.where(Transaction.priority == priority)

    # Get total before pagination
    all_txns = db.exec(query).all()
    total = len(all_txns)

    # Apply pagination
    offset = (page - 1) * PAGE_SIZE
    paginated = sorted(all_txns, key=lambda t: t.date, reverse=True)[offset:offset + PAGE_SIZE]

    return TransactionListResponse(
        transactions=[TransactionResponse.model_validate(t) for t in paginated],
        total=total,
        page=page,
        per_page=PAGE_SIZE,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_session),
):
    """Get a single transaction. user_id is required to verify ownership."""
    uid = _validate_user(user_id, db)

    try:
        tid = UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transaction_id format")

    txn = db.exec(
        select(Transaction).where(
            Transaction.id == tid,
            Transaction.user_id == uid,
        )
    ).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return TransactionResponse.model_validate(txn)


@router.post("/ingest", response_model=dict)
def trigger_ingestion(
    user_id: str = Query(...),
    persona_key: str = Query("alex"),
    db: Session = Depends(get_session),
):
    """
    Trigger transaction ingestion for a user.
    In production with Plaid/Stripe this would be webhook-driven.
    In demo mode this re-runs the synthetic adapter.
    """
    uid = _validate_user(user_id, db)

    ingester = TransactionIngester(db)
    result = ingester.ingest(user_id=uid, persona_key=persona_key)
    return result


@router.post("/override", response_model=MessageResponse)
def set_merchant_override(
    user_id: str = Query(...),
    body: MerchantOverrideCreate = ...,
    db: Session = Depends(get_session),
):
    """
    Set a merchant category override.
    Future transactions from this merchant will use the preferred category.
    """
    uid = _validate_user(user_id, db)

    existing = db.exec(
        select(MerchantOverride).where(
            MerchantOverride.user_id == uid,
            MerchantOverride.merchant_name == body.merchant_name,
        )
    ).first()

    if existing:
        existing.preferred_category = body.preferred_category
        db.add(existing)
    else:
        override = MerchantOverride(
            user_id=uid,
            merchant_name=body.merchant_name,
            preferred_category=body.preferred_category,
            created_at=datetime.utcnow(),
        )
        db.add(override)

    db.commit()
    return MessageResponse(
        message=f"Override set: '{body.merchant_name}' → '{body.preferred_category}'"
    )


@router.delete("/override", response_model=MessageResponse)
def delete_merchant_override(
    user_id: str = Query(...),
    merchant_name: str = Query(...),
    db: Session = Depends(get_session),
):
    """Remove a merchant category override."""
    uid = _validate_user(user_id, db)

    override = db.exec(
        select(MerchantOverride).where(
            MerchantOverride.user_id == uid,
            MerchantOverride.merchant_name == merchant_name,
        )
    ).first()

    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    db.delete(override)
    db.commit()
    return MessageResponse(message=f"Override removed for '{merchant_name}'")
