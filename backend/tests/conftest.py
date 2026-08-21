"""Shared test fixtures — auto-inject a fake authenticated user for all API tests."""

import warnings

import pytest
from fastapi.testclient import TestClient

# P1-5: silence Starlette's httpx deprecation until httpx2 is adopted (keeps pytest 0 warnings)
warnings.filterwarnings("ignore", message="Using `httpx`.*", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from app.auth import get_current_user
from app.main import app
from app.profile_store import reset_in_memory_store
from app.roadmap_store import reset_in_memory_roadmap_store
from app.task_store import reset_in_memory_task_store

FAKE_USER_ID = "00000000-0000-0000-0000-000000000001"


def _fake_current_user() -> str:
    return FAKE_USER_ID


@pytest.fixture(autouse=True)
def _override_auth():
    """Replace JWT verification with a deterministic fake and clear local stores."""
    reset_in_memory_store()
    reset_in_memory_roadmap_store()
    reset_in_memory_task_store()
    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    reset_in_memory_store()
    reset_in_memory_roadmap_store()
    reset_in_memory_task_store()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
