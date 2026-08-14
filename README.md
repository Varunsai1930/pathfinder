# Pathfinder

Career-path planning SaaS for Indian tech students. Pathfinder helps students explore a focused set of entry-level technology careers, understand their skill gaps, and follow a realistic learning path.

## Repository layout

- `frontend/` — React + Vite + TypeScript interface.
- `backend/` — FastAPI API and the static, versioned career catalog.
- `supabase/` — database migrations and security policies.

## Local setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The frontend works in an unauthenticated preview state until Supabase variables are supplied. The backend serves the catalog at `GET /api/v1/catalog/roles` and exposes `GET /health` for deployment checks.

## Environment variables

Never commit populated environment files. Copy the provided templates and add values from the relevant Supabase project and LLM provider when those services are configured.
# pathfinder
