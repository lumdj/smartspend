"""
SmartSpend Ingestion — Abstract Base Adapter

Defines the contract every data source adapter must fulfill.
Nothing downstream cares which adapter is active — they all
produce identical NormalizedTransaction objects.

To add a new data source:
1. Create a new file in ingestion/
2. Subclass AbstractTransactionAdapter
3. Implement fetch()
4. Register it in ingester.py
5. Add the source key to config.py DATA_SOURCE literal
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass
class NormalizedTransaction:
    """
    The single internal transaction shape every adapter must produce.
    All fields are explicitly typed — no dicts, no ambiguity.

    Security note: amounts are Decimal, never float.
    Float arithmetic is inappropriate for financial values.
    """

    # Source tracking — forms the idempotency key with user_id
    external_id: str           # The source's own identifier for this transaction
    source: str                # 'synthetic' | 'plaid' | 'stripe'

    # Core transaction data
    date: date
    merchant: str
    amount: Decimal            # Always positive. Credits handled separately.
    currency: str              # ISO 4217 lowercase e.g. 'usd'

    # Classification — source provides raw, AI enriches later
    raw_category: str
    priority: str              # 'essential' | 'semi-essential' | 'discretionary'

    # Source-specific extras — stored in transactions.metadata JSONB
    # Keeps core schema clean while preserving all original data
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate fields after construction."""
        if self.amount <= 0:
            raise ValueError(f"Transaction amount must be positive, got {self.amount}")
        if self.source not in ("synthetic", "plaid", "stripe"):
            raise ValueError(f"Unknown source: {self.source}")
        if self.priority not in ("essential", "semi-essential", "discretionary"):
            raise ValueError(f"Unknown priority: {self.priority}")
        if len(self.currency) != 3:
            raise ValueError(f"Currency must be 3-char ISO code, got: {self.currency}")
        self.currency = self.currency.lower()
        # Sanitize merchant name — strip leading/trailing whitespace
        self.merchant = self.merchant.strip()
        if not self.merchant:
            raise ValueError("Merchant name cannot be empty")
        if not self.external_id:
            raise ValueError("external_id cannot be empty")


class AbstractTransactionAdapter(ABC):
    """
    Base class for all transaction data source adapters.

    Each adapter is responsible for:
    - Fetching raw transaction data from its source
    - Normalizing it into NormalizedTransaction objects
    - Handling source-specific errors gracefully

    The adapter does NOT:
    - Write to the database (that's the ingester's job)
    - Call the Claude API (that's the claude_service's job)
    - Apply business logic (that's the analytics service's job)
    """

    @abstractmethod
    def fetch(self, user_id: UUID, **kwargs) -> list[NormalizedTransaction]:
        """
        Fetch and normalize transactions for a given user.

        Args:
            user_id: The internal UUID of the user to fetch for.
            **kwargs: Source-specific parameters (date range, account ID, etc.)

        Returns:
            List of NormalizedTransaction objects.
            Returns empty list if no transactions found — never raises on empty.

        Raises:
            ConnectionError: If the data source is unreachable.
            ValueError: If source data is malformed and cannot be normalized.
        """
        ...

    @property
    @abstractmethod
    def source_key(self) -> str:
        """
        The string identifier for this source.
        Must match the value stored in transactions.source.
        """
        ...

    def validate_connection(self) -> bool:
        """
        Optional health check — verify the source is reachable.
        Override in adapters that connect to external services.
        Default returns True (always healthy) for local sources.
        """
        return True
