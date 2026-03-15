"""
SmartSpend Claude Service

All Anthropic API calls in one place.
Every call is profile-aware — tone, depth, and framing adapt to
who the user actually is based on their onboarding profile.

Tooltip markup convention:
Claude wraps financial jargon in [[term|definition]] markup.
The frontend renders these as tap-to-expand inline tooltips.
Example: "Your [[credit utilization|% of credit limit in use]] is 67%"

Security notes:
- API key loaded from settings, never hardcoded
- User data injected as structured context, never as raw string interpolation
- All Claude responses parsed as JSON — malformed responses caught and logged
- Nudge messages truncated to 500 chars max before DB storage
"""

import json
import logging
from typing import Optional
from uuid import UUID

import anthropic

from config import get_settings
from models.orm import UserProfile

logger = logging.getLogger(__name__)
settings = get_settings()

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1000

# ── Tone Instructions ─────────────────────────────────────────────────────────

TONE_INSTRUCTIONS = {
    "gentle_encouraging": """
Tone: Warm, patient, and encouraging. This person is stressed about money.
Be their supportive coach — never their critic. Celebrate small wins.
Frame problems as solvable. Use soft language: "consider", "one option is",
"it might help to". No sarcasm or sass — just genuine care and optimism.
""",
    "direct_sassy": """
Tone: Confident, direct, and a little sassy — like a financially savvy
friend who tells it straight. This user is experienced enough to handle
honesty. Be witty but never cruel. Call out bad patterns clearly.
They can take it — and they'll respect you more for not sugarcoating it.
""",
    "balanced_coaching": """
Tone: Friendly but honest. A knowledgeable mentor — warm enough to be
approachable, direct enough to be genuinely useful. Light humor is fine.
Don't sugarcoat problems, but always pair a problem with a path forward.
""",
}

# ── Financial Education RAG Context ──────────────────────────────────────────

FINANCIAL_EDUCATION_CONTEXT = """
CREDIT FUNDAMENTALS:
- Utilization: Keep balance below 30% of limit. Above 50% is risky. Above 70% actively damages score.
- Payment history: 35% of FICO score. One missed payment hurts for 7 years.
- Minimum payments: $1,000 balance at 24% APR paying minimums = ~5 years, ~$600 extra in interest.
- Score ranges: 300-579 Poor | 580-669 Fair | 670-739 Good | 740-799 Very Good | 800+ Exceptional
- Hard inquiries: New credit application = ~5-10 point temporary drop.
- Length of history: 15% of score. Older accounts help — don't close them.

BUDGETING:
- 50/30/20: 50% needs, 30% wants, 20% savings/debt
- Emergency fund: $500-1,000 starter before aggressive savings
- Dining out: Average person spends $200-400/month — #1 easiest category to cut
- Subscription creep: Average person has 4+ forgotten subscriptions

CREDIT CARD BEST PRACTICES:
- Pay in full monthly = zero interest, best score impact
- Set up autopay for at least the minimum — protects payment history
- Review statements monthly for fraud
- Utilization resets each billing cycle — timing payments matters

LIFE STAGE NOTES:
- New to credit: Even a $500 card used lightly and paid monthly builds history
- Carrying balance: High-interest debt (20%+ APR) should be priority 1 over saving
- Working professional: Don't let rewards points justify overspending
"""


# ── System Prompt Builder ─────────────────────────────────────────────────────

def _build_system_prompt(profile: Optional[UserProfile] = None) -> str:
    """Build a dynamic system prompt tailored to the user's profile."""
    base = "You are SmartSpend's AI financial coach — knowledgeable and genuinely helpful.\n\n"

    if not profile:
        base += TONE_INSTRUCTIONS["balanced_coaching"].strip()
        base += "\n\nRules: Explain WHY things matter. Be specific. Be concise."
        return base

    # Tone based on stress level and experience
    if profile.stress_level >= 4:
        tone_key = "gentle_encouraging"
    elif profile.stress_level <= 2 and profile.credit_experience == "3_plus_years":
        tone_key = "direct_sassy"
    else:
        tone_key = "balanced_coaching"

    base += TONE_INSTRUCTIONS[tone_key].strip() + "\n\n"

    # User context
    base += f"You are speaking with {profile.name}.\n"
    base += _profile_context_summary(profile) + "\n\n"

    # Goal-specific framing
    goal_frames = {
        "build_credit": "Their primary goal is building credit — tie advice to score impact whenever possible.",
        "reduce_debt": "They are actively reducing debt — flag spending that competes with debt paydown.",
        "saving_for_something": "They are saving for a specific goal — help them see the trade-off between spending and reaching it.",
        "just_track_spending": "They want visibility and awareness — focus on clarity and patterns, not pressure.",
        "learn_financial_basics": "They are learning from scratch — briefly explain every concept. Never assume financial knowledge.",
    }
    goal_frame = goal_frames.get(profile.financial_goal, "")
    if goal_frame:
        base += f"Goal framing: {goal_frame}\n\n"

    # Weakness flagging
    if profile.spending_weakness != "none_im_disciplined":
        weakness = profile.spending_weakness.replace("_", " ")
        base += f"Watch for: '{weakness}' is their self-reported weakness — proactively flag patterns in this category.\n\n"

    # Balance behavior
    if not profile.pays_full_balance:
        base += (
            "Important: This user carries a balance and pays interest. "
            "Always factor interest costs into advice. "
            "Paying down high-APR debt often takes priority over saving.\n\n"
        )

    # Tooltip instruction
    base += (
        "Tooltip markup: Wrap financial jargon in [[term|brief definition]] format. "
        "Example: 'Your [[credit utilization|% of your credit limit currently in use]] is 67%.'\n\n"
    )

    base += "Rules: Explain WHY things matter. Reference their actual numbers. Be concise. No generic advice."
    return base


def _profile_context_summary(profile: UserProfile) -> str:
    stress_labels = {1: "relaxed", 2: "mostly calm", 3: "moderately stressed",
                     4: "quite stressed", 5: "very anxious"}
    return (
        f"Profile:\n"
        f"- Age: {profile.age_range}\n"
        f"- Status: {profile.occupation.replace('_', ' ')}\n"
        f"- Income source: {profile.income_source.replace('_', ' ')}\n"
        f"- Monthly income: {profile.monthly_income_range}\n"
        f"- Credit limit: ${float(profile.credit_limit):,.0f}\n"
        f"- Credit experience: {profile.credit_experience.replace('_', ' ')}\n"
        f"- Primary goal: {profile.financial_goal.replace('_', ' ')}\n"
        f"- Spending weakness: {profile.spending_weakness.replace('_', ' ')}\n"
        f"- Money stress: {profile.stress_level}/5 ({stress_labels.get(profile.stress_level, 'unknown')})\n"
        f"- Pays full balance: {'Yes' if profile.pays_full_balance else 'No — carries a balance'}"
    )


# ── Claude Service Class ──────────────────────────────────────────────────────

class ClaudeService:
    """
    Encapsulates all Anthropic API calls.
    Instantiate once per request in routers via Depends().
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate_insights(
        self,
        summary: dict,
        alerts: list[dict],
        profile: Optional[UserProfile] = None,
    ) -> dict:
        """
        Generate personalized spending recommendations and a credit education tip.
        Returns dict with: recommendations (list), credit_education_tip (str), health_score (int)
        """
        prompt = f"""
{FINANCIAL_EDUCATION_CONTEXT}

---
Monthly Spending Summary:
{json.dumps({k: str(v) for k, v in summary.items() if k != '_raw_transactions'}, indent=2)}

Active Alerts:
{json.dumps(alerts, indent=2)}

Generate financial coaching tailored to this user. Return ONLY this JSON:
{{
  "recommendations": [
    "specific tip 1 — reference their actual numbers",
    "specific tip 2 — tied to their stated goal or weakness",
    "specific tip 3 — one forward-looking action for next month"
  ],
  "credit_education_tip": "1-2 sentences about a credit concept relevant to their exact situation",
  "health_score": <integer 0-100>,
  "health_score_reasoning": "one sentence"
}}

JSON only. No markdown fences."""

        return self._call(prompt, profile)

    def generate_monthly_report(
        self,
        user_name: str,
        month: str,
        spending_data: dict,
        profile: Optional[UserProfile] = None,
    ) -> dict:
        """
        Generate a monthly financial health report narrative.
        Returns dict with: ai_narrative, action_items, badges_earned, biggest_risk
        """
        prompt = f"""
{FINANCIAL_EDUCATION_CONTEXT}

---
Monthly report for {user_name} — {month}:
{json.dumps({k: str(v) for k, v in spending_data.items() if k != '_raw_transactions'}, indent=2)}

Return ONLY this JSON:
{{
  "ai_narrative": "2-3 sentence narrative of this month. Reference real numbers. Match tone to profile.",
  "action_items": [
    "concrete action 1 — specific to their data",
    "concrete action 2 — addresses weakness if relevant",
    "concrete action 3 — one win to carry into next month"
  ],
  "badges_earned": ["Badge Name if genuinely earned — e.g. 'Under Budget', 'Credit Conscious'. Empty array if none."],
  "biggest_risk": "One sentence on the single most important financial risk this month."
}}

JSON only."""

        return self._call(prompt, profile)

    def generate_nudge(
        self,
        nudge_type: str,
        context: dict,
        profile: Optional[UserProfile] = None,
    ) -> str:
        """
        Generate a single contextual nudge message.
        Returns the message string, truncated to 500 chars for DB storage.
        """
        prompt = f"""
Generate a SmartSpend nudge for nudge_type='{nudge_type}'.

Context:
{json.dumps(context, indent=2)}

Write ONE message — 1-2 sentences max.
Direct but not harsh. Explain the financial consequence briefly.
Match tone to the user's profile stress level.
Use [[term|definition]] markup for any financial jargon.
Return just the message string — no JSON, no quotes."""

        result = self._call_raw(prompt, profile)
        return result[:500] if result else ""

    def generate_education_card(
        self,
        trigger_key: str,
        concept: str,
        profile: Optional[UserProfile] = None,
        summary: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """
        Generate a fully dynamic education card for a specific trigger.
        Returns dict with: title, content, one_action, one_number
        """
        spending_context = ""
        if summary:
            spending_context = f"\nCurrent spending context:\n{json.dumps({k: str(v) for k, v in summary.items() if k != '_raw_transactions'}, indent=2)}"

        prompt = f"""
{FINANCIAL_EDUCATION_CONTEXT}

---
Generate a financial education card for concept: "{concept}"
Trigger: {trigger_key}
{spending_context}

Write specifically for this user's situation, experience level, and stress level.
Use [[term|definition]] markup for any financial jargon.

Return ONLY this JSON:
{{
  "title": "Short, specific title — not generic (max 10 words)",
  "content": "2-3 paragraphs explaining the concept using their actual numbers where possible. Plain language. No jargon without tooltip markup.",
  "one_action": "The single most important thing they should do about this right now (1 sentence)",
  "one_number": "One specific number that makes the concept real for them (e.g. '$240/year in interest', '47 point score drop')"
}}

JSON only."""

        return self._call(prompt, profile)

    def classify_transaction(
        self,
        merchant: str,
        raw_category: str,
        amount: float,
        profile: Optional[UserProfile] = None,
    ) -> dict:
        """
        Classify a transaction and optionally generate a nudge.
        Returns dict with: classification, subcategory, nudge (nullable), risk_level
        """
        prompt = f"""Classify this transaction and provide a coaching nudge if warranted.

Transaction:
- Merchant: {merchant}
- Category: {raw_category}
- Amount: ${amount:.2f}

Return ONLY this JSON:
{{
  "classification": "essential" | "semi-essential" | "discretionary",
  "subcategory": "brief label (e.g. 'coffee habit', 'phone bill', 'food delivery')",
  "nudge": "1-2 sentence coaching message in SmartSpend's voice. Only include if the amount is notable or pattern is worth flagging. Return null otherwise.",
  "risk_level": "low" | "medium" | "high"
}}

JSON only."""

        return self._call(prompt, profile)

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _call(
        self,
        prompt: str,
        profile: Optional[UserProfile] = None,
    ) -> dict:
        """Make an API call expecting a JSON response. Returns parsed dict."""
        raw = self._call_raw(prompt, profile)
        try:
            # Strip markdown fences if Claude adds them despite instructions
            clean = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"Claude returned non-JSON response: {raw[:200]}... Error: {e}")
            return {}

    def _call_raw(
        self,
        prompt: str,
        profile: Optional[UserProfile] = None,
    ) -> str:
        """Make an API call and return the raw text response."""
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=_build_system_prompt(profile),
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except anthropic.RateLimitError:
            logger.warning("Anthropic rate limit hit — returning empty response")
            return ""
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error calling Claude: {e}")
            return ""


def get_claude_service() -> ClaudeService:
    """FastAPI dependency — returns a ClaudeService instance."""
    return ClaudeService()
