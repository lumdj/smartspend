"""
SmartSpend Transaction Ingester

Orchestrates the full ingestion pipeline:
1. Selects the active adapter based on DATA_SOURCE env var
2. Fetches normalized transactions from the adapter
3. Applies merchant category overrides
4. Upserts to the database (idempotent — safe to run repeatedly)
5. Returns counts for observability

Security notes:
- Upsert uses the unique constraint (user_id, external_id, source)
  so duplicate ingestion never creates duplicate records
- All amounts validated by NormalizedTransaction before DB write
- Merchant names sanitized in NormalizedTransaction.__post_init__
"""

import logging
from uuid import UUID
from datetime import date
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

from config import get_settings
from ingestion.base import AbstractTransactionAdapter, NormalizedTransaction
from ingestion.synthetic import SyntheticAdapter
from ingestion.plaid import PlaidAdapter
from ingestion.stripe import StripeAdapter
from models.orm import Transaction, MerchantOverride
from datetime import datetime

logger = logging.getLogger(__name__)

settings = get_settings()


def get_adapter() -> AbstractTransactionAdapter:
    """
    Returns the active adapter based on DATA_SOURCE environment variable.
    Called once per ingestion run — not cached, so env changes take effect.
    """
    adapters = {
        "synthetic": SyntheticAdapter,
        "plaid": PlaidAdapter,
        "stripe": StripeAdapter,
    }

    adapter_class = adapters.get(settings.data_source)
    if not adapter_class:
        raise ValueError(
            f"Unknown DATA_SOURCE: '{settings.data_source}'. "
            f"Valid options: {list(adapters.keys())}"
        )

    return adapter_class()


class TransactionIngester:
    """
    Coordinates fetching, normalizing, and persisting transactions.

    Usage:
        ingester = TransactionIngester(db_session)
        result = ingester.ingest(user_id, persona_key="alex")
        print(f"Inserted {result['inserted']}, skipped {result['skipped']}")
    """

    def __init__(self, session: Session):
        self.session = session
        self.adapter = get_adapter()

    def ingest(
        self,
        user_id: UUID,
        **adapter_kwargs,
    ) -> dict:
        """
        Full ingestion pipeline for a user.

        Returns:
            {
                "inserted": int,   # New transactions added
                "skipped": int,    # Duplicates skipped
                "errors": int,     # Transactions that failed validation
                "source": str,     # Which adapter was used
            }
        """
        logger.info(
            f"Starting ingestion for user {user_id} "
            f"via {self.adapter.source_key} adapter"
        )

        # Fetch normalized transactions from the adapter
        try:
            normalized = self.adapter.fetch(user_id, **adapter_kwargs)
        except NotImplementedError as e:
            logger.error(f"Adapter not implemented: {e}")
            raise
        except Exception as e:
            logger.error(f"Adapter fetch failed for user {user_id}: {e}")
            raise

        if not normalized:
            logger.info(f"No transactions returned for user {user_id}")
            return {"inserted": 0, "skipped": 0, "errors": 0, "source": self.adapter.source_key}

        # Load merchant overrides for this user once — avoid N+1 queries
        overrides = self._load_merchant_overrides(user_id)

        inserted = 0
        skipped = 0
        errors = 0

        for txn in normalized:
            try:
                was_inserted = self._upsert_transaction(user_id, txn, overrides)
                if was_inserted:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                logger.warning(
                    f"Failed to upsert transaction {txn.external_id} "
                    f"for user {user_id}: {e}"
                )
                continue

        self.session.commit()

        result = {
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "source": self.adapter.source_key,
        }
        logger.info(f"Ingestion complete for user {user_id}: {result}")
        return result

    def _upsert_transaction(
        self,
        user_id: UUID,
        txn: NormalizedTransaction,
        overrides: dict[str, str],
    ) -> bool:
        """
        Insert a transaction if it doesn't already exist.
        Uses the unique constraint (user_id, external_id, source) for idempotency.

        Returns True if inserted, False if skipped (already exists).
        """
        # Apply merchant category override if one exists for this merchant
        raw_category = overrides.get(txn.merchant.lower(), txn.raw_category)

        # Check if already exists — SELECT before INSERT to avoid exception overhead
        existing = self.session.exec(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.external_id == txn.external_id,
                Transaction.source == txn.source,
            )
        ).first()

        if existing:
            return False

        db_txn = Transaction(
            user_id=user_id,
            external_id=txn.external_id,
            source=txn.source,
            date=txn.date,
            merchant=txn.merchant,
            amount=txn.amount,
            currency=txn.currency,
            raw_category=raw_category,
            priority=txn.priority,
            ai_category=None,     # Populated later by Claude service
            ai_nudge=None,        # Populated later by Claude service
            txn_metadata=txn.metadata,
            created_at=datetime.utcnow(),
        )

        self.session.add(db_txn)
        return True

    def _load_merchant_overrides(self, user_id: UUID) -> dict[str, str]:
        """
        Load all merchant category overrides for a user.
        Keys are lowercase merchant names for case-insensitive matching.

        Returns empty dict if no overrides exist.
        """
        overrides = self.session.exec(
            select(MerchantOverride).where(
                MerchantOverride.user_id == user_id
            )
        ).all()

        return {
            override.merchant_name.lower(): override.preferred_category
            for override in overrides
        }

    def health_check(self) -> dict:
        """
        Verify the active adapter can reach its data source.
        Used by the /health endpoint.
        """
        return {
            "adapter": self.adapter.source_key,
            "healthy": self.adapter.validate_connection(),
        }