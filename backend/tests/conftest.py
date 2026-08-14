"""Shared test fixtures — auto-inject a fake authenticated user for all API tests."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app

FAKE_USER_ID = "00000000-0000-0000-0000-000000000001"


def _fake_current_user() -> str:
    return FAKE_USER_ID


@pytest.fixture(autouse=True)
def _override_auth():
    """Replace JWT verification with a deterministic fake for every test."""
    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
