# SmartSpend — Architecture

## Overview

SmartSpend is a full-stack web application with a FastAPI backend, PostgreSQL database, and React frontend. The architecture is designed around three principles:

1. **Source-agnostic data ingestion** — the app is built to accept transaction data from any source (synthetic, Plaid, Stripe) through a consistent adapter interface, with no changes required to downstream services.
2. **Profile-aware AI** — every Claude API call is contextualized with the user's demographic profile, financial goals, stress level, and credit experience. The AI adapts its tone and advice to who it's actually talking to.
3. **Education through context** — financial literacy is delivered inline at the moment it's relevant, not as a separate feature users have to seek out.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   DATA INGESTION LAYER                   │
│                                                         │
│   SyntheticAdapter   PlaidAdapter*   StripeAdapter*     │
│          └──────────────┴──────────────┘                │
│                   TransactionIngester                   │
│           (normalizes all sources to NormalizedTxn)     │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   POSTGRESQL DATABASE                    │
│                                                         │
│  users          user_profiles      transactions         │
│  goals          goal_progress      achievements         │
│  user_achievements  nudges         education_cards      │
│  user_education_cards  merchant_overrides               │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                    SERVICE LAYER                         │
│                                                         │
│   AnalyticsService    AlertService    GoalService       │
│          └──────────────┴──────────────┘                │
│                    ClaudeService                        │
│         (reads from services, injects user profile)     │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                      API LAYER                           │
│                                                         │
│  /profile  /transactions  /insights  /reports           │
│  /goals    /achievements  /nudges    /demo              │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   REACT FRONTEND                         │
│                                                         │
│  Onboarding → Dashboard → Transactions → Goals          │
│  Monthly Recap → Achievements → Demo Controls           │
└─────────────────────────────────────────────────────────┘

* Stubbed for future integration
```

---

## Database Schema

### 13 Tables

**Identity**
- `users` — bare identity anchor (id, created_at)
- `user_profiles` — full onboarding data: demographics, financial context, goals, stress level, billing cycle

**Financial Data**
- `transactions` — source-agnostic transaction records with idempotency key `(user_id, external_id, source)`
- `merchant_overrides` — user corrections to AI categorization; remembered per merchant

**Goals**
- `goals` — up to 3 active goals per user; supports linked category for auto-progress tracking
- `goal_progress_snapshots` — time-series progress records; source field tracks manual vs. auto vs. recap deposit

**Gamification**
- `achievements` — catalog of achievement definitions; mix of seeded core + DB-defined custom
- `user_achievements` — join table with unlock timestamp and triggering context (JSONB)

**Engagement**
- `nudges` — AI-generated message queue; shown_at/dismissed_at pattern for notification state; includes feedback field

**Education**
- `education_cards` — trigger catalog (what fires what concept)
- `user_education_cards` — Claude-generated card instances per user; fully dynamic at trigger time

### Key Design Decisions

**JSONB for metadata and context**
Transaction `metadata` stores source-specific fields (Plaid account IDs, Stripe charge IDs) without polluting the core schema. Achievement `context` stores the exact data that triggered the unlock for auditability and display.

**Idempotent ingestion**
The unique constraint on `(user_id, external_id, source)` means the ingestion pipeline can be run repeatedly without creating duplicate transactions. This is essential for eventual Plaid/Stripe webhook integration where duplicate delivery is expected.

**Billing cycle awareness**
`user_profiles.billing_cycle_day` is nullable. When set, utilization calculations use the billing window. When null, the app falls back to calendar month with a UI prompt to configure it. Users are never blocked on this.

**Active goal cap**
Enforced at the service layer, not the database. Max 3 goals where `status = 'active'` per user. This is a product decision (paradox of choice) not a technical constraint.

---

## Ingestion Layer — Adapter Pattern

```
backend/ingestion/
├── base.py          AbstractTransactionAdapter
│                    defines: fetch() → list[NormalizedTransaction]
├── synthetic.py     SyntheticAdapter
│                    reads from seed JSON, maps to NormalizedTransaction
├── plaid.py         PlaidAdapter (stubbed)
│                    would call Plaid /transactions/get
└── stripe.py        StripeAdapter (stubbed)
                     would consume Stripe Issuing webhook events
```

The `TransactionIngester` orchestrator selects the active adapter from the `DATA_SOURCE` environment variable. Changing from `synthetic` to `plaid` in production requires only an env var change — zero code modifications.

All adapters produce a `NormalizedTransaction` object with identical fields regardless of source. Everything downstream — the analytics service, Claude service, and API layer — only ever sees `NormalizedTransaction`.

---

## AI Layer — Profile-Aware Prompting

Every Claude API call passes through `_build_system_prompt(profile)` which constructs a dynamic system prompt containing:

1. **Tone instructions** — derived from `stress_level` and `credit_experience`:
   - Stress 4–5 → `gentle_encouraging` (no sass, supportive framing)
   - Stress 1–2 + 3+ years experience → `direct_sassy` (honest, witty)
   - Everyone else → `balanced_coaching`

2. **User context summary** — occupation, income source, credit limit, financial goal, spending weakness, balance payment behavior

3. **Goal framing** — each financial goal type changes how advice is anchored (e.g., `build_credit` ties every nudge back to score impact)

4. **Financial education RAG context** — key credit fundamentals injected into every prompt so Claude can reference accurate numbers without hallucinating

### Tooltip Markup Convention

Claude wraps financial jargon in `[[term|definition]]` markup:

```
"Your [[credit utilization|The % of your credit limit currently in use. 
Bureaus check this monthly.]] is 67% — that's in the caution zone."
```

The frontend parses this markup and renders tap-to-expand inline tooltips. No separate glossary table required.

---

## Education Card System

Education cards are triggered by behavioral milestones detected in the analytics service. Each trigger:

1. Checks `user_education_cards` — skip if already received
2. Calls `ClaudeService.generate_education_card(trigger_key, profile, context)`
3. Claude generates: title, content (with tooltip markup), one concrete action, one memorable number
4. Stored in `user_education_cards`, queued as a nudge with type `education_card`
5. Surfaced to the user at next app open

Cards are fully dynamic — Claude generates them in the context of the user's actual numbers, not generic content.

---

## Demo Architecture

A `/demo` route in the frontend (unlisted, not in nav) provides a control panel for live demonstrations. Demo-specific API endpoints under `/demo/` allow:

- Loading pre-configured user personas (Alex, Jordan, Taylor)
- Triggering spending spikes in specific categories
- Fast-forwarding goal progress
- Firing specific education card triggers
- Running a monthly recap for any month
- Resetting all data for a user

This is intentional product tooling, not a hack — it enables clean, scripted demos without manual database manipulation.

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Frontend | Vercel | Auto-deploys from `main`, root: `frontend/` |
| Backend API | Render Web Service | Start: `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Database | Render PostgreSQL | Free tier, connection via `DATABASE_URL` env var |

### Environment Variables

**Backend (Render)**
```
DATABASE_URL          Provided by Render PostgreSQL
ANTHROPIC_API_KEY     Anthropic console
DATA_SOURCE           synthetic | plaid | stripe
```

**Frontend (Vercel)**
```
VITE_API_URL          https://your-app.onrender.com
```

### Migration Strategy

Alembic manages schema migrations. On every deploy, Render runs:
```
alembic upgrade head
```
before starting the web service. New team members run the same command locally to get a schema-accurate database. In production, schema changes are never applied manually.

---

## Future State

| Feature | What's needed |
|---|---|
| Plaid integration | Implement `PlaidAdapter.fetch()`, add OAuth flow to frontend |
| Stripe Issuing | Implement `StripeAdapter`, add webhook endpoint |
| Push notifications | Add FCM token to `user_profiles`, background job for nudge delivery |
| Learn tab | Browse `user_education_cards` history, add static content to `education_cards` |
| Multi-card support | Add `credit_cards` table, link transactions to card |
| CSV import | Add `CSVAdapter` to ingestion layer |
