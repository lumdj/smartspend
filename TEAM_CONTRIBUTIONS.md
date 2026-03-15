# Team Contributions

## SmartSpend — [Course Name] [Semester Year]

---

## Team Members

| Name | Role | GitHub |
|---|---|---|
| [Name 1] | Project Lead / Backend | @username |
| [Name 2] | Frontend / UI | @username |
| [Name 3] | AI / NLP Integration | @username |
| [Name 4] | Data / Analytics | @username |

---

## Contribution Breakdown

### [Name 1] — Project Lead / Backend

**Primary responsibilities:**
- Project architecture and technical decisions
- FastAPI backend setup and structure
- Database schema design (SQLModel + PostgreSQL)
- Alembic migration setup
- Transaction ingestion adapter pattern
- Deployment configuration (Render)

**Key files:**
- `backend/main.py`
- `backend/database.py`
- `backend/models/orm.py`
- `backend/ingestion/`
- `alembic/`

---

### [Name 2] — Frontend / UI

**Primary responsibilities:**
- React application setup (Vite + TailwindCSS)
- Onboarding flow component
- Dashboard layout and health score display
- Transaction feed with category badges and nudges
- Goal progress UI and monthly recap screen
- Demo control panel

**Key files:**
- `frontend/src/pages/`
- `frontend/src/components/`
- `frontend/src/hooks/`

---

### [Name 3] — AI / NLP Integration

**Primary responsibilities:**
- Anthropic Claude API integration
- Profile-aware prompt engineering
- Tone adaptation system (gentle / balanced / sassy)
- Education card generation pipeline
- Tooltip markup convention and parsing
- Nudge generation and queuing logic

**Key files:**
- `backend/services/claude_service.py`
- `backend/routers/insights.py`
- `backend/routers/nudges.py`

---

### [Name 4] — Data / Analytics

**Primary responsibilities:**
- Synthetic transaction data generator
- Analytics service (spending summaries, utilization, deltas)
- Alert detection logic (rule-based thresholds)
- Goal progress auto-tracking
- Achievement trigger evaluation
- Monthly recap computation

**Key files:**
- `backend/data/generate_synthetic.py`
- `backend/services/analytics.py`
- `backend/services/alerts.py`
- `backend/services/goals.py`

---

## Shared Contributions

The following were collaborative efforts across the team:

- Product requirements and user flow design
- Database schema finalization
- Demo persona design (Alex, Jordan, Taylor)
- README and documentation
- Testing and QA
- Demo video production

---

## Notes

> *Update this file with actual contribution details before submission. Be specific — vague entries like "helped with frontend" are not useful for graders or for your own portfolio.*
