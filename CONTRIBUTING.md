# Contributing to Pathfinder

Thank you for your interest in contributing to Pathfinder! We welcome contributions, bug reports, and feature suggestions to help make tech career navigation accessible and effective.

## Code of Conduct

Please be respectful, constructive, and collaborative in all communications and code reviews.

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/<your-username>/pathfinder.git
   cd pathfinder
   ```
3. **Set up local environments**:
   ```bash
   make setup
   ```
   This will prepare `backend/.env` and `frontend/.env.local` from the provided example templates without overwriting existing configs.

## Development Workflow

### Backend (Python / FastAPI)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

### Frontend (React / Vite / TypeScript)
```bash
cd frontend
npm install
npm run dev
```

## Running Tests & Linters

Ensure all checks pass before submitting a pull request:

```bash
# Run backend tests
make backend-test

# Run frontend tests
make frontend-test

# Run linters
make backend-lint
make frontend-lint

# Or run pre-commit across all files
make pre-commit
```

## Pull Request Guidelines

- Create a feature branch with a descriptive name (`git checkout -b feature/career-assessment-filter` or `fix/task-toggle-state`).
- Keep PRs focused on a single change or fix.
- Ensure all tests and linters pass cleanly.
- Include unit tests for any new endpoints, models, or UI components.
- Write clear, concise commit messages.

## Reporting Issues

If you encounter a bug or have a suggestion, please open an issue on GitHub:
- Include a clear title and description.
- Provide step-by-step instructions to reproduce the bug.
- Mention your environment (OS, browser, Python/Node versions).
