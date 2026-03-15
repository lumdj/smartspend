"""
SmartSpend Ingestion — Stripe Adapter (Stubbed)

This adapter is intentionally not implemented in v1.
It documents the full integration contract for future implementation.

Stripe Issuing is the relevant Stripe product — it allows platforms
to issue their own credit cards and receive webhook events for
every transaction in real time.

To activate:
1. Install stripe: `pip install stripe`
2. Add to .env: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
3. Implement fetch() and the webhook handler below
4. Set DATA_SOURCE=stripe in environment
5. Register webhook endpoint with Stripe dashboard

Stripe Issuing docs: https://stripe.com/docs/issuing
"""

from uuid import UUID
from decimal import Decimal
from datetime import date
from ingestion.base import AbstractTransactionAdapter, NormalizedTransaction
import logging

logger = logging.getLogger(__name__)

# Stripe Issuing merchant category codes (MCC) → SmartSpend priority
# Full MCC list: https://stripe.com/docs/issuing/categories
STRIPE_MCC_MAP = {
    # Essential
    "5411": ("groceries", "essential"),       # Grocery Stores
    "5912": ("health", "essential"),           # Drug Stores / Pharmacies
    "5541": ("transportation", "essential"),   # Service Stations (Gas)
    "4111": ("transportation", "essential"),   # Local / Suburban Transit
    "4121": ("transportation", "essential"),   # Taxicabs / Limousines
    "4814": ("utilities", "essential"),        # Telecom Services
    "4900": ("utilities", "essential"),        # Utilities — Electric, Gas
    # Semi-essential
    "7941": ("fitness", "semi-essential"),     # Athletic Fields / Sports Clubs
    "7997": ("fitness", "semi-essential"),     # Health Clubs
    # Discretionary
    "5812": ("dining", "discretionary"),       # Eating Places / Restaurants
    "5814": ("coffee", "discretionary"),       # Fast Food Restaurants
    "5691": ("shopping", "discretionary"),     # Men's and Women's Clothing
    "5732": ("shopping", "discretionary"),     # Electronics Stores
    "5945": ("shopping", "discretionary"),     # Hobby / Toy / Game Shops
    "7832": ("entertainment", "discretionary"), # Motion Picture Theaters
    "5999": ("shopping", "discretionary"),     # Miscellaneous Retail
    "7929": ("entertainment", "discretionary"), # Bands / Orchestras / Misc Entertainment
    "5921": ("nightlife", "discretionary"),    # Package Stores / Beer, Wine, Liquor
}

DEFAULT_CATEGORY = ("other", "discretionary")


class StripeAdapter(AbstractTransactionAdapter):
    """
    Fetches transaction data from Stripe Issuing webhooks.

    NOT IMPLEMENTED in v1 — stubbed for future integration.

    Unlike Plaid (which polls for transactions), Stripe Issuing
    pushes events in real time via webhooks. The integration model is:

    1. Stripe sends POST to /webhooks/stripe when a card is used
    2. Webhook handler verifies signature and stores raw event
    3. This adapter normalizes stored events into NormalizedTransaction objects
    4. Ingester upserts them into the transactions table
    """

    source_key = "stripe"

    def __init__(self):
        # These will be loaded from settings when implemented
        # from config import get_settings
        # settings = get_settings()
        # self.stripe_key = settings.stripe_secret_key
        # self.webhook_secret = settings.stripe_webhook_secret
        # stripe.api_key = self.stripe_key
        pass

    def fetch(
        self,
        user_id: UUID,
        cardholder_id: str = None,    # Stripe Issuing cardholder ID
        start_date: str = None,
        end_date: str = None,
        **kwargs,
    ) -> list[NormalizedTransaction]:
        """
        Fetch Stripe Issuing transactions for a cardholder.

        STUB — raises NotImplementedError until implemented.

        When implemented, this will call:
        stripe.issuing.Transaction.list(cardholder=cardholder_id)

        Example Stripe Issuing transaction shape:
        {
            "id": "ipi_abc123",
            "amount": -575,                    # Negative = debit in Stripe (cents)
            "currency": "usd",
            "merchant_data": {
                "name": "Starbucks",
                "category": "eating_places_restaurants",
                "category_code": "5812",
            },
            "created": 1710000000,             # Unix timestamp
            "cardholder": "ich_xyz",
        }
        """
        raise NotImplementedError(
            "Stripe integration is not yet implemented. "
            "Set DATA_SOURCE=synthetic in your .env to use synthetic data."
        )

    def normalize_webhook_event(self, event: dict) -> NormalizedTransaction | None:
        """
        Normalize a raw Stripe Issuing webhook event into a NormalizedTransaction.

        Called by the webhook endpoint handler at /webhooks/stripe.
        Returns None if the event type is not a transaction event.

        Stripe sends many event types — we only care about:
        - issuing_transaction.created
        - issuing_authorization.created (for pending auth visibility)
        """
        if event.get("type") not in (
            "issuing_transaction.created",
            "issuing_authorization.created",
        ):
            return None

        txn_data = event["data"]["object"]
        merchant = txn_data.get("merchant_data", {})
        mcc = merchant.get("category_code", "")
        category, priority = self._map_mcc(mcc)

        # Stripe amounts are in cents, negative for debits
        amount_cents = abs(txn_data.get("amount", 0))
        amount = Decimal(str(amount_cents)) / Decimal("100")

        if amount <= 0:
            return None

        import datetime
        created_ts = txn_data.get("created", 0)
        txn_date = datetime.datetime.utcfromtimestamp(created_ts).date()

        return NormalizedTransaction(
            external_id=txn_data["id"],
            source="stripe",
            date=txn_date,
            merchant=merchant.get("name", "Unknown Merchant"),
            amount=amount,
            currency=txn_data.get("currency", "usd").lower(),
            raw_category=category,
            priority=priority,
            metadata={
                "cardholder_id": txn_data.get("cardholder"),
                "mcc": mcc,
                "stripe_category": merchant.get("category"),
                "event_type": event.get("type"),
            },
        )

    def _map_mcc(self, mcc: str) -> tuple[str, str]:
        """Map a Stripe MCC code to SmartSpend category + priority."""
        return STRIPE_MCC_MAP.get(str(mcc), DEFAULT_CATEGORY)

    def validate_connection(self) -> bool:
        """NOT IMPLEMENTED — returns False until credentials are configured."""
        logger.warning("Stripe adapter is not configured. Returning False for health check.")
        return False
