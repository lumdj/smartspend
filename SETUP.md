# SmartSpend — Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (local) or a Render PostgreSQL instance
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
DATABASE_URL=postgresql://postgres:password@localhost:5432/smartspend
ANTHROPIC_API_KEY=sk-ant-...
DATA_SOURCE=synthetic
```

> **Note:** Never commit `.env` to GitHub. It is already in `.gitignore`.

### Create the local database

```bash
# Using psql
psql -U postgres -c "CREATE DATABASE smartspend;"
```

### Run database migrations

```bash
alembic upgrade head
```

This creates all 13 tables and seeds the achievements catalog and education card triggers.

### Seed synthetic transaction data

```bash
python data/seed.py
```

This loads 3 pre-configured demo users (Alex, Jordan, Taylor) with 90 days of realistic transaction history.

### Start the backend

```bash
uvicorn main:app --reload
```

API is running at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## 3. Frontend Setup

```bash
# New terminal from project root
cd frontend
npm install
```

### Configure environment variables

```bash
cp .env.example .env
```

```env
VITE_API_URL=http://localhost:8000
```

### Start the frontend

```bash
npm run dev
```

App is running at `http://localhost:5173`

---

## 4. Verify Everything is Working

1. Open `http://localhost:5173` — you should see the SmartSpend onboarding screen
2. Open `http://localhost:8000/docs` — you should see the FastAPI Swagger UI
3. In Swagger, call `GET /transactions/users` — you should see Alex, Jordan, and Taylor

If transactions are empty, re-run `python data/seed.py` from the backend directory.

---

## 5. Demo Control Panel

Navigate to `http://localhost:5173/demo` to access the demo control panel.

This page is not linked in the main navigation — it's for live demonstrations only. Use it to:
- Switch between pre-configured personas
- Trigger spending alerts and education cards
- Run monthly recaps
- Reset user data between demos

---

## Deployment

### Render (Backend + Database)

1. Create a new **PostgreSQL** instance on Render — copy the `DATABASE_URL`
2. Create a new **Web Service** on Render:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Add environment variables in Render dashboard:
   - `DATABASE_URL` — from step 1
   - `ANTHROPIC_API_KEY` — your key
   - `DATA_SOURCE` — `synthetic`
4. After first deploy, run the seed script via Render Shell: `python data/seed.py`

### Vercel (Frontend)

1. Import your GitHub repo in Vercel
2. Set root directory to `frontend`
3. Add environment variable:
   - `VITE_API_URL` — your Render backend URL (e.g. `https://smartspend-api.onrender.com`)
4. Deploy

### Keeping the Backend Awake (Free Tier)

Render's free tier spins down after 15 minutes of inactivity, causing a ~30 second cold start. To prevent this during your demo period:

1. Create a free account at [uptimerobot.com](https://uptimerobot.com)
2. Add a new HTTP monitor pointing to `https://your-app.onrender.com/health`
3. Set interval to 10 minutes

---

## Troubleshooting

**`alembic upgrade head` fails — can't connect to database**
Check that PostgreSQL is running locally and your `DATABASE_URL` in `.env` is correct.

**`ANTHROPIC_API_KEY` errors**
Verify the key is set in `.env` and the file is being loaded. The backend uses `python-dotenv` — make sure you're running `uvicorn` from the `backend/` directory.

**Frontend shows blank dashboard / no data**
Make sure `VITE_API_URL` points to the running backend and the seed script has been run.

**CORS errors in browser console**
The backend allows `localhost:5173` by default. If you're running the frontend on a different port, add it to the `allow_origins` list in `main.py`.
