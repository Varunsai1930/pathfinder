# Pathfinder

Career-path planning SaaS for tech students. Pathfinder maps a short interest-and-skills assessment onto four entry-level technology roles, shows a transparent fit breakdown, and produces a milestone-based learning roadmap.

Supported roles: Frontend Developer, Backend Developer, Data Analyst, Cloud/DevOps Engineer.

Repository: https://github.com/Varunsai1930/pathfinder

## What you can do in the app

1. Sign in with email (Supabase OTP).
2. Describe your goal in plain words — Pathfinder drafts the assessment from it (conversational front door), or skip and fill it in yourself.
3. Review the three-section assessment draft: interests, skills, constraints.
4. See ranked role cards with Pathfinder fit scores, reasons, and skill gaps.
5. Open a career-path dashboard with milestones, a weekly plan, and task checkboxes.

## Repository layout

- `frontend/` — React + Vite + TypeScript UI.
- `backend/` — FastAPI API, static career catalog, matching engine, roadmap/task persistence.
- `supabase/` — Postgres schema, RLS policies, and later table migrations.
- `docs/` — Solution documentation outline for the Round 2 write-up.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer (npm)
- A Supabase project (Auth + Postgres) for the signed-in flow

The backend still boots without live Supabase credentials. Profile, match, roadmap, and task writes then stay in memory, which is enough for unit tests. The frontend can render without Supabase variables, but sign-in and saved progress need them.

## Local setup

### 1. Database

In the Supabase SQL editor, run the migrations in order:

1. `supabase/migrations/20260813000000_initial_schema.sql`
2. `supabase/migrations/20260816000000_roadmaps.sql`
3. `supabase/migrations/20260816010000_tasks.sql`
4. `supabase/migrations/20260820000000_llm_personalization.sql`

Enable email OTP under Authentication → Providers → Email.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Fill `backend/.env` from the Supabase project (Settings → API):

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `PATHFINDER_CORS_ORIGINS` — include `http://localhost:5173`

Then start the API:

```bash
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/health`
Public catalog: `GET http://localhost:8000/api/v1/catalog/roles`

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
```

Set `frontend/.env.local`:

- `VITE_API_URL=http://localhost:8000`
- `VITE_SUPABASE_URL` — same project URL as the backend
- `VITE_SUPABASE_ANON_KEY` — the publishable/anon key only (never the service role key)

Then:

```bash
npm run dev
```

Open http://localhost:5173.

## Tests

From `backend/` with the virtualenv active:

```bash
pytest
```

These cover catalog loading, representative-profile matching, profile/match endpoints, and roadmap/task persistence.

## Authenticated API

All of the following require a Supabase JWT in `Authorization: Bearer <token>`. The user id always comes from the verified token, never from the request body.

- `POST /api/v1/intake` — turn a free-text career goal into reviewable assessment pre-fill hints
- `POST /api/v1/profile` — save assessment answers
- `GET /api/v1/profile` — load the saved profile
- `POST /api/v1/match` — rank the four roles from the saved profile
- `POST /api/v1/roadmaps/{role_id}` — create or refresh the selected role roadmap
- `GET /api/v1/roadmaps/{role_id}` — load roadmap, milestones, and task state
- `PATCH /api/v1/tasks/{task_id}` — toggle a task and return the next action
- `POST /api/v1/questions` — answer a short question from the caller's match data and, optionally, an owned roadmap (`question`, optional `role_id`)

Compatibility aliases also exist at `/profile` and `/roadmaps/{role_id}`.

## Environment files

Never commit populated `.env` files. Copy the templates:

- `backend/.env.example`
- `frontend/.env.example`

## Grounded AI guidance

Pathfinder's fit scores, skill gaps, milestones, tasks, and next actions are always deterministic. If `OPENROUTER_API_KEY` is configured, the API uses a pinned OpenRouter model (see `openrouter_model` in `backend/app/config.py`) for constrained enhancements:

- assessment pre-fill hints from a free-text goal (`POST /api/v1/intake`) — the model returns dimension-level hints and deterministic code maps them to editable per-question suggestions;
- two-to-three sentence fit explanations;
- a personalized focus and pacing note for the five existing milestones; and
- a small learner Q&A response based only on that learner's computed match and optional roadmap.

Every model response is validated with strict Pydantic schemas and checked against the caller's real role and milestone IDs (skill IDs for intake). An unavailable key, timeout, malformed response, rate limit, or unknown reference returns deterministic fallback guidance instead. The model is pinned rather than using an auto-router so evaluation behavior stays reproducible.

After adding `OPENROUTER_API_KEY` and deploying the backend, verify that the personalization path is live with an authenticated request; the response must contain `"generation_mode": "llm"`:

```bash
curl -X POST "$API_URL/api/v1/match" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

## Deploy notes

- Frontend: Vercel (`frontend/vercel.json`)
- Backend: Railway (`backend/railway.toml`)
- In production, set `PATHFINDER_CORS_ORIGINS` to the live frontend origin (and localhost only if you still need it)
