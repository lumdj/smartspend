# SmartSpend 💳

> AI-powered budgeting and financial education for people who are tired of not understanding their money.

SmartSpend helps students, recent graduates, and first-time credit card users understand not just *what* they're spending — but *why it matters* and *what to do about it*. Instead of showing you charts and leaving you to figure it out, SmartSpend explains your financial picture in plain language, connects your spending to goals you actually care about, and teaches credit fundamentals in context — not in a textbook.

---

## The Problem

Most budgeting apps give you data without direction. You can see that you spent $340 on dining last month, but the app doesn't tell you that this is 28% of your income, that it's competing with your goal to move out, or that carrying a balance on top of this is costing you an extra $200/year in interest. SmartSpend does.

---

## Features

### 🧠 AI Financial Coaching
Personalized insights powered by Claude. Every nudge explains the *why* behind the observation — not just what you did, but what it means for your credit score, your goals, and your future.

### 📊 Spending Dashboard
Real-time breakdown of essential vs. discretionary spending, credit utilization indicator, and a Financial Health Score (0–100) updated monthly.

### 🎯 Goal Tracking
Set up to 3 active financial goals — a trip, an emergency fund, a big purchase. Link goals to spending categories and watch your savings progress update automatically. Monthly recap lets you consciously allocate savings into goal buckets.

### 🏆 Achievements & Gamification
Earn badges for real financial behavior — staying under 30% utilization, paying your full balance, hitting 50% of a goal. Achievements unlock contextual education cards that explain the concept behind the win.

### 📚 Contextual Financial Education
No Learn tab. No articles you won't read. Financial concepts are explained inline, at the moment they're relevant to your actual situation. Credit terms are tap-to-expand. Education cards trigger when you hit meaningful milestones.

### 🔔 Smart Nudges
AI-generated alerts for spending spikes, credit limit proximity, and goal opportunities. Tone adapts to your stress level — gentle and encouraging for anxious users, direct and sassy for confident ones.

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
├── backend/                  # FastAPI application
│   ├── main.py               # App entry point
│   ├── database.py           # DB connection and session
│   ├── models/
│   │   ├── orm.py            # SQLModel table definitions
│   │   └── schemas.py        # Pydantic request/response models
│   ├── ingestion/            # Data ingestion adapter pattern
│   │   ├── base.py           # Abstract adapter interface
│   │   ├── synthetic.py      # Synthetic data adapter
│   │   ├── plaid.py          # Plaid adapter (stubbed)
│   │   └── stripe.py         # Stripe adapter (stubbed)
│   ├── routers/              # API route handlers
│   ├── services/             # Business logic
│   ├── alembic/              # Database migrations
│   ├── data/                 # Seed data
│   └── requirements.txt
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── hooks/
│   └── package.json
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
uvicorn main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

---

## Team

See [TEAM_CONTRIBUTIONS.md](./TEAM_CONTRIBUTIONS.md) for individual contributions.

---

## License

MIT — see [LICENSE](./LICENSE)
