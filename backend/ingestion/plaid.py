"""
SmartSpend Ingestion — Plaid Adapter (Stubbed)

This adapter is intentionally not implemented in v1.
It documents the full integration contract for future implementation.

To activate:
1. Install plaid-python: `pip install plaid-python`
2. Add to .env: PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV
3. Implement fetch() below
4. Set DATA_SOURCE=plaid in environment
5. Add OAuth link flow to frontend

Plaid docs: https://plaid.com/docs/transactions/
"""

from uuid import UUID
from ingestion.base import AbstractTransactionAdapter, NormalizedTransaction
import logging

logger = logging.getLogger(__name__)

# Plaid category → SmartSpend priority mapping
# Full Plaid category list: https://plaid.com/docs/api/products/transactions/#categorization
PLAID_CATEGORY_MAP = {
    # Essential
    "Food and Drink / Supermarkets and Groceries": ("groceries", "essential"),
    "Healthcare / Pharmacies": ("health", "essential"),
    "Healthcare / Hospitals": ("health", "essential"),
    "Transportation / Gas Stations": ("transportation", "essential"),
    "Transportation / Taxi": ("transportation", "essential"),
    "Transportation / Ride Share": ("transportation", "essential"),
    "Utilities / Electric": ("utilities", "essential"),
    "Utilities / Water": ("utilities", "essential"),
    "Utilities / Telecom": ("utilities", "essential"),
    "Rent": ("rent", "essential"),
    # Semi-essential
    "Service / Subscription": ("subscriptions", "semi-essential"),
    "Recreation / Gyms and Fitness Centers": ("fitness", "semi-essential"),
    # Discretionary
    "Food and Drink / Restaurants": ("dining", "discretionary"),
    "Food and Drink / Coffee Shop": ("coffee", "discretionary"),
    "Food and Drink / Food Delivery Services": ("dining", "discretionary"),
    "Shops / Clothing and Accessories": ("shopping", "discretionary"),
    "Shops / Sporting Goods": ("shopping", "discretionary"),
    "Shops / Electronics": ("shopping", "discretionary"),
    "Entertainment": ("entertainment", "discretionary"),
    "Travel": ("travel", "discretionary"),
    "Nightlife": ("nightlife", "discretionary"),
    "Personal Care": ("beauty", "discretionary"),
}

DEFAULT_CATEGORY = ("other", "discretionary")


class PlaidAdapter(AbstractTransactionAdapter):
    """
    Fetches real transaction data via the Plaid API.

    NOT IMPLEMENTED in v1 — stubbed for future integration.
    The interface contract is fully defined so implementation
    requires only filling in the fetch() method body.
    """

    source_key = "plaid"

    def __init__(self):
        # These will be loaded from settings when implemented
        # from config import get_settings
        # settings = get_settings()
        # self.client_id = settings.plaid_client_id
        # self.secret = settings.plaid_secret
        # self.environment = settings.plaid_environment
        pass

    def fetch(
        self,
        user_id: UUID,
        access_token: str = None,
        start_date: str = None,   # YYYY-MM-DD
        end_date: str = None,     # YYYY-MM-DD
        **kwargs,
    ) -> list[NormalizedTransaction]:
        """
        Fetch transactions from Plaid for a linked bank account.

        STUB — raises NotImplementedError until implemented.

        When implemented, this method will:
        1. Call plaid_client.transactions_get(access_token, start_date, end_date)
        2. Handle Plaid's pagination (cursor-based for /transactions/sync)
        3. Map Plaid categories to SmartSpend priority tiers
        4. Return NormalizedTransaction objects

        Example Plaid response shape:
        {
            "transaction_id": "abc123",
            "name": "Starbucks",
            "amount": 5.75,           # Positive = debit in Plaid
            "date": "2025-03-15",
            "category": ["Food and Drink", "Coffee Shop"],
            "merchant_name": "Starbucks",
            "account_id": "xyz789",
        }
        """
        raise NotImplementedError(
            "Plaid integration is not yet implemented. "
            "Set DATA_SOURCE=synthetic in your .env to use synthetic data."
        )

    def _map_category(self, plaid_categories: list[str]) -> tuple[str, str]:
        """
        Map Plaid's hierarchical category list to SmartSpend's flat category + priority.

        Plaid returns categories as a list from broad to specific:
        ["Food and Drink", "Restaurants", "Pizza"]
        We join the first two levels and look up in the map.
        """
        if not plaid_categories:
            return DEFAULT_CATEGORY

        key = " / ".join(plaid_categories[:2])
        return PLAID_CATEGORY_MAP.get(key, DEFAULT_CATEGORY)

    def validate_connection(self) -> bool:
        """
        Verify Plaid credentials are valid.
        NOT IMPLEMENTED — returns False until credentials are configured.
        """
        logger.warning("Plaid adapter is not configured. Returning False for health check.")
        return False
