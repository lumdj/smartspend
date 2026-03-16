# SmartSpend — Architecture

## Overview

SmartSpend is a full-stack web application with a FastAPI backend, PostgreSQL database, and React frontend. The architecture is designed around three principles:

1. **Source-agnostic data ingestion** — the app accepts transaction data from any source (synthetic, Plaid, Stripe) through a consistent adapter interface, with no changes required to downstream services.
2. **Profile-aware AI** — every Claude API call is contextualized with the user's demographic profile, financial goals, stress level, and credit experience. The AI adapts its tone and advice to who it's actually talking to.
3. **Education through context** — financial literacy is delivered inline at the moment it's relevant, not as a separate feature users have to seek out.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   DATA INGESTION LAYER                       │
│                                                             │
│   SyntheticAdapter   PlaidAdapter*   StripeAdapter*         │
│          └──────────────┴──────────────┘                    │
│                   TransactionIngester                       │
│           (normalizes all sources to NormalizedTxn)         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   POSTGRESQL DATABASE                        │
│                                                             │
│  users          user_profiles      transactions             │
│  goals          goal_progress      achievements             │
│  user_achievements  nudges         education_cards          │
│  user_education_cards  merchant_overrides                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    SERVICE LAYER                             │
│                                                             │
│   AnalyticsService    AlertService    GoalService           │
│   AchievementsService  EducationService                     │
│          └──────────────┴──────────────┘                    │
│                    ClaudeService                            │
│         (reads from services, injects user profile)         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      API LAYER                               │
│                                                             │
│  /profile    /transactions   /insights    /reports          │
│  /goals      /nudges         /achievements                  │
│  /education  /health-history /demo                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   REACT FRONTEND                             │
│                                                             │
│  Onboarding → Dashboard (Health Chart) → Transactions       │
│  Goals → Achievements → Recap → Learning → Demo Controls    │
└─────────────────────────────────────────────────────────────┘

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
- `achievements` — catalog of 15 achievement definitions; mix of seeded core + DB-defined custom
- `user_achievements` — join table with unlock timestamp and triggering context (JSONB)

**Engagement**
- `nudges` — AI-generated message queue; shown_at/dismissed_at pattern for notification state; includes 👍👎 feedback field

**Education**
- `education_cards` — trigger catalog (12 trigger definitions seeded on startup)
- `user_education_cards` — Claude-generated card instances per user; fully dynamic at trigger time

---

## Ingestion Layer — Adapter Pattern

```
backend/ingestion/
├── base.py          AbstractTransactionAdapter
│                    defines: fetch() → list[NormalizedTransaction]
├── synthetic.py     SyntheticAdapter
│                    3 personas: Alex (stressed undergrad), Jordan (recent grad), Taylor (working pro)
│                    Deterministic — same UUID always produces same transaction history
├── plaid.py         PlaidAdapter (stubbed)
│                    would call Plaid /transactions/get
└── stripe.py        StripeAdapter (stubbed)
                     would consume Stripe Issuing webhook events
```

The `TransactionIngester` orchestrator selects the active adapter from the `DATA_SOURCE` environment variable. Changing from `synthetic` to `plaid` in production requires only an env var change — zero code modifications.

---

## AI Layer — Profile-Aware Prompting

Every Claude API call passes through `_build_system_prompt(profile)` which constructs a dynamic system prompt containing:

1. **Tone instructions** — derived from `stress_level` and `credit_experience`:
   - Stress 4–5 → `gentle_encouraging` (supportive, no sass)
   - Stress 1–2 + 3+ years experience → `direct_sassy` (honest, witty)
   - Everyone else → `balanced_coaching`

2. **User context summary** — occupation, income, credit limit, financial goal, spending weakness, balance behavior

3. **Goal framing** — each financial goal type changes how advice is anchored

4. **Financial education RAG context** — key credit fundamentals injected into every prompt

### Tooltip Markup Convention

Claude wraps financial jargon in `[[term|definition]]` markup:

```
"Your [[credit utilization|% of your credit limit currently in use]] is 67%"
```

The frontend parses this and renders tap-to-expand inline tooltips.

---

## Health Score Calculation

The Financial Health Score (0–100) is computed from three weighted components:

| Component | Weight | Full score condition |
|---|---|---|
| Credit utilization | 40 pts | Under 30% |
| Discretionary ratio | 30 pts | Under 40% of total spend |
| Income ratio | 30 pts | Under 60% of monthly income |

Alert penalties: -5 per critical alert, -2 per warning alert.

The `/health-history/` endpoint retroactively computes this score for each month with transaction data, enabling the 6-month trend chart on the dashboard.

---

## Education Card System

Education cards are triggered by behavioral milestones:

1. Analytics service detects a trigger condition (e.g. utilization crosses 50%)
2. Checks `user_education_cards` — skip if already received
3. Calls `ClaudeService.generate_education_card(trigger_key, profile, context)`
4. Claude generates: title, content (with tooltip markup), one concrete action, one memorable number
5. Stored in `user_education_cards`, queued as a nudge
6. Surfaced in the Learning tab

12 triggers are seeded: utilization thresholds, goal milestones, first full balance month, dining spikes, subscription creep, income overspend, stress level, and first month complete.

Reading 5 cards unlocks the **Knowledge Seeker** achievement, tracked server-side on the `/education/{id}/viewed` endpoint.

---

## Demo Architecture

A `/demo` route in the frontend (unlisted, not in nav) provides a control panel for live demonstrations:

- **Load persona** — clears transactions and loads Alex, Jordan, or Taylor's spending profile
- **Reset** — wipes all generated data and reloads with a fresh persona
- **Spike category** — inflates a spending category by a multiplier to trigger alerts
- **Trigger education card** — manually fires any of the 12 education card triggers, generating a Claude-written card instantly

### Demo Personas

| Persona | Profile | Best for showing |
|---|---|---|
| Alex | Stressed undergrad, high dining, near credit limit | Alerts, danger zone education cards, high utilization |
| Jordan | Recent grad, moderate spend, one active goal | Goal tracking, balanced coaching, monthly recap |
| Taylor | Working professional, disciplined, low stress | Clean health score, achievements, improving trend |

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Frontend | Vercel | Auto-deploys from `main`, root: `frontend/` |
| Backend API | Render Web Service | Start: `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Database | Render PostgreSQL | Free tier, connection via `DATABASE_URL` env var |

### Keep-Alive
Render's free tier spins down after 15 minutes of inactivity. Use UptimeRobot to ping `GET /health` every 10 minutes to prevent cold starts during demos.

### Environment Variables

**Backend (Render)**
```
DATABASE_URL          Provided by Render PostgreSQL
ANTHROPIC_API_KEY     Anthropic console
DATA_SOURCE           synthetic
ENVIRONMENT           production
ALLOWED_ORIGINS       https://your-app.vercel.app
```

**Frontend (Vercel)**
```
VITE_API_URL          https://your-app.onrender.com
```

---

## Known Compatibility Notes

- SQLModel requires `nullable` to be set on `Column()` directly, not on `Field()` when `sa_column` is provided
- The `metadata` field name conflicts with SQLModel internals — renamed to `txn_metadata` in the ORM with `Column('metadata', JSONB)` to preserve the DB column name
- `httpx` must be pinned to `0.27.2` for compatibility with the Anthropic SDK
- Run `pip freeze > requirements.txt` after any dependency changes to ensure Render gets identical versions

---

## Future State

| Feature | What's needed |
|---|---|
| Plaid integration | Implement `PlaidAdapter.fetch()`, add OAuth flow to frontend |
| Stripe Issuing | Implement `StripeAdapter`, add webhook endpoint |
| Push notifications | Add FCM token to `user_profiles`, background job for nudge delivery |
| Multi-card support | Add `credit_cards` table, link transactions to card |
| CSV import | Add `CSVAdapter` to ingestion layer |
| Health score persistence | Store score snapshots to `health_score_history` table for long-term trends |
