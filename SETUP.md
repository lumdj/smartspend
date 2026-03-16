# SmartSpend — Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Git

---

## 1. Clone the Repository

```bash
git clone https://github.com/your-org/smartspend.git
cd smartspend
```

---

## 2. Backend Setup

### Install dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
DATABASE_URL=postgresql://your_username@localhost:5432/smartspend
ANTHROPIC_API_KEY=sk-ant-...
DATA_SOURCE=synthetic
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:5173
```

> **Mac note:** Homebrew PostgreSQL uses your Mac username as the default role, not `postgres`. Run `whoami` to get your username and use that in the DATABASE_URL. If you want to use `postgres`, run: `psql -U your_username -c "CREATE ROLE postgres WITH SUPERUSER LOGIN;"`

### Create the local database

```bash
# Using your Mac username
psql -U your_username -c "CREATE DATABASE smartspend;"

# Or if you created the postgres role
psql -U postgres -c "CREATE DATABASE smartspend;"
```

### Run database migrations

```bash
alembic upgrade head
```

You should see:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial_schema
```

### Seed the database

```bash
python data/seed.py
```

Expected output:
```
Seeding achievements...
  ✓ 15 achievements seeded
Seeding education card triggers...
  ✓ 12 education card triggers seeded

Seed complete.
```

### Start the backend

```bash
uvicorn main:app --reload
```

API running at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
```

`.env` should contain:
```env
VITE_API_URL=http://localhost:8000
```

```bash
npm run dev
```

App running at `http://localhost:5173`

---

## 4. Verify Everything Works

Open `http://localhost:5173` — you should see the onboarding flow.

Complete onboarding with any profile. After submitting you'll land on the dashboard with synthetic transaction data already loaded.

Quick API verification:
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"healthy","adapter":"synthetic","adapter_healthy":true,...}`

---

## 5. Demo Control Panel

Navigate to `http://localhost:5173/demo` — this page is not linked in the nav.

Use it to:
- Switch between Alex, Jordan, and Taylor spending personas
- Spike category spending to trigger alerts
- Fire education card triggers to populate the Learning tab
- Reset user data between demos

---

## 6. Dependency Notes

The following versions are pinned for compatibility — do not upgrade without testing:

```
httpx==0.27.2          # Required for Anthropic SDK compatibility
```

If you add packages, always run `pip freeze > requirements.txt` before committing so Render gets identical versions.

---

## Deployment

### Render (Backend + Database)

1. Create a **PostgreSQL** instance on Render — copy the `DATABASE_URL`
2. Create a **Web Service**:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `alembic upgrade head && python data/seed.py && uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Add environment variables:
   - `DATABASE_URL` — from step 1
   - `ANTHROPIC_API_KEY` — your key
   - `DATA_SOURCE` — `synthetic`
   - `ENVIRONMENT` — `production`
   - `ALLOWED_ORIGINS` — your Vercel URL
4. Deploy

### Vercel (Frontend)

1. Import your GitHub repo
2. Set root directory to `frontend`
3. Add environment variable: `VITE_API_URL` = your Render backend URL
4. Deploy

### Keep Backend Alive (Free Tier)

Render free tier spins down after 15 minutes of inactivity — the first request after that takes ~30 seconds. Prevent this for your demo:

1. Sign up at [uptimerobot.com](https://uptimerobot.com) (free)
2. Add HTTP monitor: `https://your-app.onrender.com/health`
3. Set interval: 10 minutes

---

## Troubleshooting

**`alembic upgrade head` fails — connection refused**
Check PostgreSQL is running: `brew services list | grep postgresql`

**`RuntimeError: Passing nullable is not supported`**
You have an old version of `orm.py`. The fix is removing `nullable=` from any `Field()` that also uses `sa_column=`.

**`Client.__init__() got an unexpected keyword argument 'proxies'`**
httpx version conflict. Run: `pip install httpx==0.27.2`

**Dashboard shows no data after onboarding**
Initial ingestion may have failed silently. In Swagger UI call `POST /transactions/ingest?user_id=YOUR_ID&persona_key=alex`

**Recap page shows nothing / CORS error**
Usually a 500 on the backend masking as CORS. Check uvicorn terminal for the actual Python error.

**Education cards not appearing in Learning tab**
Cards only generate when triggers fire. Use the demo control panel at `/demo` → "Trigger Education Cards" to fire them manually.
