"""Tests for the deprecated legacy compatibility routes at the API root."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

SAMPLE_PAYLOAD = {
    "interest_responses": {
        "realistic-1": 5, "realistic-2": 4, "realistic-3": 3,
        "investigative-1": 2, "investigative-2": 1, "investigative-3": 5,
        "artistic-1": 4, "artistic-2": 3, "artistic-3": 2,
        "social-1": 1, "social-2": 5, "social-3": 4,
        "enterprising-1": 3, "enterprising-2": 2, "enterprising-3": 1,
        "conventional-1": 5, "conventional-2": 4, "conventional-3": 3,
    },
    "skill_confidence": {"python": "practised", "javascript": "project-ready", "sql": "aware", "git": "project-ready"},
    "work_style_responses": {
        "analytical": 5, "creative": 3, "collaborative": 4, "structured": 4, "systems_oriented": 5
    },
    "constraints": {"hours_per_week": 15, "target_timeline_weeks": 12, "career_certainty": "deciding"},
}

DEPRECATION_LOGGER = "pathfinder.deprecations"


def _deprecation_warnings(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    return [
        record
        for record in records
        if record.name == DEPRECATION_LOGGER and record.levelno == logging.WARNING
    ]


def test_legacy_routes_marked_deprecated_in_openapi(client: TestClient) -> None:
    """All four compatibility aliases must be flagged deprecated=True."""
    openapi = client.get("/openapi.json").json()
    legacy = {
        path: {method.upper(): op for method, op in ops.items()}
        for path, ops in openapi["paths"].items()
        if path in ("/profile", "/roadmaps/{role_id}")
    }

    assert set(legacy) == {"/profile", "/roadmaps/{role_id}"}
    assert set(legacy["/profile"]) == {"GET", "POST"}
    assert set(legacy["/roadmaps/{role_id}"]) == {"GET", "POST"}
    for path, methods in legacy.items():
        for method, operation in methods.items():
            assert operation.get("deprecated") is True, f"{method} {path} is not marked deprecated"


def test_versioned_routes_are_not_deprecated(client: TestClient) -> None:
    """The canonical /api/v1 routes stay first-class citizens."""
    openapi = client.get("/openapi.json").json()

    for path, ops in openapi["paths"].items():
        if path.startswith("/api/v1"):
            for method, operation in ops.items():
                assert operation.get("deprecated") is not True, f"{method.upper()} {path}"


def test_legacy_profile_post_still_works_and_warns(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=DEPRECATION_LOGGER):
        response = client.post("/profile", json=SAMPLE_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["constraints"] == SAMPLE_PAYLOAD["constraints"]
    warnings = _deprecation_warnings(caplog.records)
    assert len(warnings) == 1
    assert getattr(warnings[0], "endpoint", None) == "POST /profile"
    assert getattr(warnings[0], "replacement", None) == "POST /api/v1/profile"


def test_legacy_profile_get_still_works_and_warns(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    assert client.post("/api/v1/profile", json=SAMPLE_PAYLOAD).status_code == 200

    with caplog.at_level(logging.WARNING, logger=DEPRECATION_LOGGER):
        response = client.get("/profile")

    assert response.status_code == 200
    warnings = _deprecation_warnings(caplog.records)
    assert len(warnings) == 1
    assert getattr(warnings[0], "endpoint", None) == "GET /profile"


def test_legacy_roadmap_routes_still_work_and_warn(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    assert client.post("/api/v1/profile", json=SAMPLE_PAYLOAD).status_code == 200

    with caplog.at_level(logging.WARNING, logger=DEPRECATION_LOGGER):
        created = client.post("/roadmaps/frontend-developer")
        fetched = client.get("/roadmaps/frontend-developer")

    assert created.status_code == 200
    assert fetched.status_code == 200
    assert created.json()["role_id"] == fetched.json()["role_id"] == "frontend-developer"
    warnings = _deprecation_warnings(caplog.records)
    assert [getattr(w, "endpoint", None) for w in warnings] == [
        "POST /roadmaps/{role_id}",
        "GET /roadmaps/{role_id}",
    ]


def test_versioned_routes_do_not_warn(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """Canonical /api/v1 traffic must never trip the deprecation logger."""
    with caplog.at_level(logging.WARNING, logger=DEPRECATION_LOGGER):
        assert client.post("/api/v1/profile", json=SAMPLE_PAYLOAD).status_code == 200
        assert client.get("/api/v1/profile").status_code == 200
        assert client.post("/api/v1/roadmaps/frontend-developer").status_code == 200
        assert client.get("/api/v1/roadmaps/frontend-developer").status_code == 200

    assert _deprecation_warnings(caplog.records) == []
