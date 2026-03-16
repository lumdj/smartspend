# SmartSpend 💳

> AI-powered budgeting and financial education for people who are tired of not understanding their money.

SmartSpend helps students, recent graduates, and first-time credit card users understand not just *what* they're spending — but *why it matters* and *what to do about it*. Instead of showing you charts and leaving you to figure it out, SmartSpend explains your financial picture in plain language, connects your spending to goals you actually care about, and teaches credit fundamentals in context — not in a textbook.

---

## The Problem

Most budgeting apps give you data without direction. You can see that you spent $340 on dining last month, but the app doesn't tell you that this is 28% of your income, that it's competing with your goal to move out, or that carrying a balance on top of this is costing you an extra $200/year in interest. SmartSpend does.

---

## Features

### 📈 Financial Health Score + Trend Chart
A 0–100 health score computed from utilization, spending mix, and income ratio. A live area chart shows your score trend over the past 6 months with a directional indicator (↑ improving, ↓ declining) so you can see if you're actually making progress.

### 🧠 AI Financial Coaching
Personalized insights powered by Claude. Every nudge explains the *why* behind the observation — not just what you did, but what it means for your credit score, your goals, and your future. Tone adapts to your stress level — gentle and encouraging for anxious users, direct and honest for confident ones.

### 📊 Spending Dashboard
Real-time breakdown of essential vs. discretionary spending, credit utilization indicator, and billing-cycle-aware calculations.

### 🎯 Goal Tracking
Set up to 3 active financial goals — a trip, an emergency fund, a big purchase. Link goals to spending categories and watch your savings progress update automatically. Monthly recap lets you consciously allocate savings into goal buckets.

### 📚 Contextual Financial Education
A dedicated Learning tab surfaces AI-generated education cards triggered by your financial behavior — when you cross 50% utilization, create your first goal, or complete a month. Each card is written specifically for you with a memorable number and one concrete action. Tap any financial term for an inline tooltip definition.

### 🏆 Achievements & Gamification
Earn badges for real financial behavior — staying under 30% utilization, paying your full balance, hitting 50% of a goal, reading 5 education cards. Achievements are tracked in your profile and visible on the Achievements page.

### 🔔 Smart Nudges
AI-generated alerts for spending spikes, credit limit proximity, and goal opportunities, surfaced on the dashboard with 👍👎 feedback buttons.

### 🎮 Demo Control Panel
A hidden `/demo` route provides a control panel for live demonstrations — load pre-configured spending personas, spike category spending to trigger alerts, and fire specific education card triggers on demand.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TailwindCSS, Recharts |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| ORM | SQLModel + Alembic |
| AI | Anthropic Claude API |
| Deployment | Vercel (frontend), Render (backend + DB) |

---

## Live Demo

- **App:** [smartspend.vercel.app](https://smartspend.vercel.app) *(update before submission)*
- **API:** [smartspend-api.onrender.com](https://smartspend-api.onrender.com)
- **API Docs:** [smartspend-api.onrender.com/docs](https://smartspend-api.onrender.com/docs)

---

## Repository Structure

```
smartspend/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── orm.py               # All 13 SQLModel table definitions
│   │   └── schemas.py           # Pydantic request/response models
│   ├── ingestion/               # Adapter pattern data ingestion
│   │   ├── base.py              # Abstract adapter interface
│   │   ├── synthetic.py         # Synthetic data (3 personas)
│   │   ├── plaid.py             # Plaid adapter (stubbed)
│   │   └── stripe.py            # Stripe adapter (stubbed)
│   ├── routers/
│   │   ├── profile.py
│   │   ├── transactions.py
│   │   ├── education.py         # Education cards + learning tab
│   │   ├── health_history.py    # Health score trend chart data
│   │   └── remaining_routers.py # insights, reports, goals, nudges, achievements, demo
│   ├── services/
│   │   ├── analytics.py
│   │   ├── alerts.py
│   │   ├── goals.py
│   │   ├── achievements.py
│   │   ├── education.py
│   │   └── claude_service.py
│   └── data/
│       └── seed.py
│
├── frontend/
│   └── src/
│       ├── api/client.js
│       ├── hooks/
│       │   ├── useProfile.js
│       │   └── useData.js
│       ├── components/
│       │   ├── layout/Layout.jsx
│       │   └── dashboard/HealthScoreChart.jsx
│       └── pages/
│           ├── Onboarding.jsx
│           ├── Dashboard.jsx
│           └── Pages.jsx        # Transactions, Goals, Achievements, Recap, Learning, Demo
│
├── README.md
├── ARCHITECTURE.md
├── SETUP.md
├── USER_GUIDE.md
├── TEAM_CONTRIBUTIONS.md
└── LICENSE
```

---

## Quick Start

See [SETUP.md](./SETUP.md) for full local development instructions.

```bash
# Clone
git clone https://github.com/your-org/smartspend.git
cd smartspend

# Backend
cd backend
cp .env.example .env        # add your keys
pip install -r requirements.txt
alembic upgrade head
python data/seed.py
uvicorn main:app --reload

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env
npm run dev
```

---

## Team

See [TEAM_CONTRIBUTIONS.md](./TEAM_CONTRIBUTIONS.md) for individual contributions.

---

## License

MIT — see [LICENSE](./LICENSE)
