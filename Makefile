# Pathfinder developer workflow. Targets are self-contained: run from the repo root.

.PHONY: setup backend-test frontend-test backend-lint frontend-lint pre-commit

# Copy .env.example files into place the first time (never overwrite an existing .env).
setup:
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
	@echo "Environment files ready (existing files were left untouched)."

# Backend: deterministic FastAPI test suite (pytest, configured in backend/pyproject.toml).
backend-test:
	cd backend && .venv/bin/pytest

# Frontend: Vitest unit tests (component/data-layer, src/**/*.test.tsx).
frontend-test:
	cd frontend && npm run test

# Lint parity with the pre-commit hooks.
backend-lint:
	cd backend && .venv/bin/ruff check app tests

frontend-lint:
	cd frontend && npm run lint

# Run every hook across the whole repo, exactly as CI would.
pre-commit:
	pre-commit run --all-files
