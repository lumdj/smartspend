"""
SmartSpend Ingestion — Synthetic Data Adapter

Generates realistic student credit card transaction data for
development, testing, and demo purposes.

Three pre-configured personas:
- Alex Chen       stressed undergrad, high dining, near credit limit
- Jordan Rivera   recent grad, moderate spend, one active goal
- Taylor Kim      working professional, low stress, disciplined spender

Security note: This adapter generates deterministic data based on
user_id so the same user always gets the same transaction history.
No real financial data is ever used or stored.
"""

import hashlib
import json
import os
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from ingestion.base import AbstractTransactionAdapter, NormalizedTransaction


# ── Merchant Templates ────────────────────────────────────────────────────────
# (merchant_name, raw_category, priority, amount_min, amount_max)

ESSENTIAL_MERCHANTS = [
    ("Walmart", "groceries", "essential", 25, 90),
    ("Trader Joe's", "groceries", "essential", 30, 75),
    ("Kroger", "groceries", "essential", 20, 85),
    ("CVS Pharmacy", "health", "essential", 8, 45),
    ("Walgreens", "health", "essential", 5, 40),
    ("Shell Gas Station", "transportation", "essential", 30, 65),
    ("Chevron", "transportation", "essential", 28, 60),
    ("Uber", "transportation", "essential", 8, 25),
    ("Lyft", "transportation", "essential", 7, 22),
    ("AT&T", "utilities", "essential", 45, 80),
    ("Verizon", "utilities", "essential", 50, 85),
    ("PG&E", "utilities", "essential", 40, 120),
    ("Safeway", "groceries", "essential", 22, 88),
    ("Target Grocery", "groceries", "essential", 30, 95),
]

SEMI_ESSENTIAL_MERCHANTS = [
    ("Spotify", "subscriptions", "semi-essential", 10, 10),
    ("Netflix", "subscriptions", "semi-essential", 15, 15),
    ("Hulu", "subscriptions", "semi-essential", 8, 18),
    ("Adobe Creative Cloud", "subscriptions", "semi-essential", 20, 55),
    ("Planet Fitness", "fitness", "semi-essential", 10, 25),
    ("LA Fitness", "fitness", "semi-essential", 25, 40),
    ("Microsoft 365", "subscriptions", "semi-essential", 10, 10),
    ("iCloud Storage", "subscriptions", "semi-essential", 3, 10),
    ("Amazon Prime", "subscriptions", "semi-essential", 15, 15),
]

DISCRETIONARY_MERCHANTS = [
    ("Chipotle", "dining", "discretionary", 10, 18),
    ("Starbucks", "coffee", "discretionary", 5, 12),
    ("McDonald's", "dining", "discretionary", 6, 15),
    ("Chick-fil-A", "dining", "discretionary", 8, 16),
    ("Panera Bread", "dining", "discretionary", 9, 18),
    ("DoorDash", "dining", "discretionary", 15, 45),
    ("Uber Eats", "dining", "discretionary", 12, 40),
    ("Domino's Pizza", "dining", "discretionary", 14, 35),
    ("Dutch Bros", "coffee", "discretionary", 5, 10),
    ("Boba Tea Shop", "coffee", "discretionary", 6, 12),
    ("SHEIN", "shopping", "discretionary", 15, 80),
    ("Amazon", "shopping", "discretionary", 12, 120),
    ("Target", "shopping", "discretionary", 20, 95),
    ("H&M", "shopping", "discretionary", 18, 75),
    ("Sephora", "beauty", "discretionary", 15, 90),
    ("Ulta Beauty", "beauty", "discretionary", 12, 65),
    ("AMC Theaters", "entertainment", "discretionary", 12, 30),
    ("Steam", "entertainment", "discretionary", 5, 60),
    ("Ticketmaster", "entertainment", "discretionary", 30, 150),
    ("Nike", "shopping", "discretionary", 40, 150),
    ("Lululemon", "shopping", "discretionary", 50, 130),
    ("Bar Tab", "nightlife", "discretionary", 20, 80),
    ("Postmates", "dining", "discretionary", 12, 38),
]

ALL_MERCHANTS = ESSENTIAL_MERCHANTS + SEMI_ESSENTIAL_MERCHANTS + DISCRETIONARY_MERCHANTS

# ── Persona Profiles ──────────────────────────────────────────────────────────
# Each persona seeds a different spending pattern for demo purposes.

PERSONAS = {
    "alex": {
        "name": "Alex Chen",
        "description": "Stressed undergrad — high dining, near credit limit",
        # Weights: more discretionary, heavy dining + coffee
        "merchant_weights": {
            "essential": 0.25,
            "semi-essential": 0.15,
            "discretionary": 0.60,
        },
        "dining_multiplier": 1.8,    # spends more on dining than average
        "txns_per_day_weights": [15, 35, 30, 15, 5],  # 0,1,2,3,4 txns/day
        "spike_probability": 0.08,   # 8% chance of amount spike
    },
    "jordan": {
        "name": "Jordan Rivera",
        "description": "Recent grad — moderate spend, working toward goals",
        "merchant_weights": {
            "essential": 0.45,
            "semi-essential": 0.20,
            "discretionary": 0.35,
        },
        "dining_multiplier": 1.0,
        "txns_per_day_weights": [20, 40, 25, 12, 3],
        "spike_probability": 0.04,
    },
    "taylor": {
        "name": "Taylor Kim",
        "description": "Working professional — disciplined, low stress",
        "merchant_weights": {
            "essential": 0.55,
            "semi-essential": 0.25,
            "discretionary": 0.20,
        },
        "dining_multiplier": 0.7,
        "txns_per_day_weights": [25, 40, 25, 8, 2],
        "spike_probability": 0.02,
    },
}


class SyntheticAdapter(AbstractTransactionAdapter):
    """
    Generates deterministic synthetic transaction data.

    Determinism is achieved by seeding the RNG with a hash of the
    user_id — same user always gets the same transaction history,
    which is essential for consistent demo behavior.
    """

    source_key = "synthetic"

    def __init__(self, months: int = 3):
        self.months = months

    def fetch(
        self,
        user_id: UUID,
        persona_key: str = "alex",
        **kwargs,
    ) -> list[NormalizedTransaction]:
        """
        Generate synthetic transactions for a user.

        Args:
            user_id: Internal user UUID (used to seed RNG for determinism)
            persona_key: Which spending persona to use ('alex'|'jordan'|'taylor')
            **kwargs: Ignored — present for interface compatibility

        Returns:
            List of NormalizedTransaction objects sorted newest first.
        """
        if persona_key not in PERSONAS:
            raise ValueError(
                f"Unknown persona '{persona_key}'. "
                f"Valid options: {list(PERSONAS.keys())}"
            )

        persona = PERSONAS[persona_key]

        # Seed RNG deterministically from user_id
        # This ensures the same user always gets the same transaction history
        seed_int = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed_int)

        transactions = []
        end_date = date.today()
        start_date = end_date - timedelta(days=30 * self.months)
        current_date = start_date
        txn_counter = 1

        while current_date <= end_date:
            num_txns = rng.choices(
                [0, 1, 2, 3, 4],
                weights=persona["txns_per_day_weights"]
            )[0]

            for _ in range(num_txns):
                merchant_data = self._pick_merchant(rng, persona)
                merchant, category, priority, amount_min, amount_max = merchant_data

                amount = Decimal(
                    str(round(rng.uniform(amount_min, amount_max), 2))
                )

                # Apply dining multiplier for personas with different dining habits
                if category == "dining":
                    amount = (amount * Decimal(str(persona["dining_multiplier"]))).quantize(
                        Decimal("0.01")
                    )

                # Occasional spending spike — simulates real overspend moments
                if rng.random() < persona["spike_probability"]:
                    multiplier = Decimal(str(round(rng.uniform(1.8, 3.2), 2)))
                    amount = (amount * multiplier).quantize(Decimal("0.01"))

                # Build a stable external_id from the deterministic sequence
                external_id = f"syn_{str(user_id)[:8]}_{current_date.isoformat()}_{txn_counter:04d}"

                try:
                    txn = NormalizedTransaction(
                        external_id=external_id,
                        source="synthetic",
                        date=current_date,
                        merchant=merchant,
                        amount=amount,
                        currency="usd",
                        raw_category=category,
                        priority=priority,
                        metadata={
                            "persona": persona_key,
                            "generated": True,
                        },
                    )
                    transactions.append(txn)
                    txn_counter += 1
                except ValueError:
                    # Skip malformed transactions rather than crashing
                    continue

            current_date += timedelta(days=1)

        # Sort newest first — matches expected API response order
        transactions.sort(key=lambda t: t.date, reverse=True)
        return transactions

    def _pick_merchant(
        self,
        rng: random.Random,
        persona: dict,
    ) -> tuple:
        """Select a merchant weighted by the persona's spending profile."""
        weights = persona["merchant_weights"]

        # Pick priority tier first
        tier = rng.choices(
            ["essential", "semi-essential", "discretionary"],
            weights=[
                weights["essential"],
                weights["semi-essential"],
                weights["discretionary"],
            ]
        )[0]

        merchant_pool = {
            "essential": ESSENTIAL_MERCHANTS,
            "semi-essential": SEMI_ESSENTIAL_MERCHANTS,
            "discretionary": DISCRETIONARY_MERCHANTS,
        }[tier]

        return rng.choice(merchant_pool)

    def validate_connection(self) -> bool:
        """Synthetic adapter is always available — no external dependency."""
        return True

    def get_persona_summary(self) -> dict:
        """Return persona descriptions for the demo control panel."""
        return {
            key: {
                "name": p["name"],
                "description": p["description"],
            }
            for key, p in PERSONAS.items()
        }
