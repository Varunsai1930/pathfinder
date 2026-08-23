"""Tests for authenticated profile management (POST /profile and GET /profile)."""

from fastapi.testclient import TestClient
import pytest

from app.auth import get_current_user
from app.main import app

USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"


def _sample_payload(hours: int = 15, certainty: str = "deciding") -> dict:
    return {
        "interest_responses": {
            "q1": 5,
            "q2": 4,
            "q3": 3,
            "q4": 2,
            "q5": 1,
            "q6": 5,
            "q7": 4,
            "q8": 3,
            "q9": 2,
            "q10": 1,
            "q11": 5,
            "q12": 4,
            "q13": 3,
            "q14": 2,
            "q15": 1,
            "q16": 5,
            "q17": 4,
            "q18": 3,
        },
        "skill_confidence": {
            "python": "practised",
            "javascript": "project-ready",
            "sql": "aware",
            "git": "project-ready",
        },
        "work_style_responses": {
            "analytical": 5,
            "creative": 3,
            "collaborative": 4,
            "structured": 4,
            "systems_oriented": 5,
        },
        "constraints": {
            "hours_per_week": hours,
            "target_timeline_weeks": 12,
            "career_certainty": certainty,
        },
    }


def test_profile_unauthenticated_requests_rejected() -> None:
    """Both POST and GET /profile require valid authentication header."""
    app.dependency_overrides.clear()
    raw_client = TestClient(app)

    # API v1 path
    get_res = raw_client.get("/api/v1/profile")
    assert get_res.status_code in (401, 403)

    post_res = raw_client.post("/api/v1/profile", json=_sample_payload())
    assert post_res.status_code in (401, 403)

    # Root path
    get_root = raw_client.get("/profile")
    assert get_root.status_code in (401, 403)

    post_root = raw_client.post("/profile", json=_sample_payload())
    assert post_root.status_code in (401, 403)


def test_profile_not_found_returns_clean_404(client: TestClient) -> None:
    """GET /profile returns 404 if user has not yet submitted an assessment."""
    response = client.get("/api/v1/profile")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_profile_authenticated_roundtrip(client: TestClient) -> None:
    """POST /profile then GET /profile returns exact persisted profile payload."""
    payload = _sample_payload(hours=20, certainty="committed")
    expected = {**payload, "goal_text": None}

    # POST /profile
    post_res = client.post("/api/v1/profile", json=payload)
    assert post_res.status_code == 200
    assert post_res.json() == expected

    # GET /profile returns the exact same payload
    get_res = client.get("/api/v1/profile")
    assert get_res.status_code == 200
    assert get_res.json() == expected

    # Direct root path also returns identical payload
    get_root = client.get("/profile")
    assert get_root.status_code == 200
    assert get_root.json() == expected


def test_profile_resubmission_overwrites_existing_record(client: TestClient) -> None:
    """Resubmitting an assessment overwrites the existing row instead of erroring."""
    initial_payload = _sample_payload(hours=10, certainty="exploring")
    first_res = client.post("/api/v1/profile", json=initial_payload)
    assert first_res.status_code == 200
    assert first_res.json()["constraints"]["hours_per_week"] == 10

    # Resubmit with updated hours and certainty
    updated_payload = _sample_payload(hours=25, certainty="committed")
    updated_payload["skill_confidence"]["docker"] = "project-ready"
    second_res = client.post("/api/v1/profile", json=updated_payload)
    assert second_res.status_code == 200
    assert second_res.json()["constraints"]["hours_per_week"] == 25
    assert second_res.json()["skill_confidence"]["docker"] == "project-ready"

    # GET confirms updated data is returned
    get_res = client.get("/api/v1/profile")
    assert get_res.status_code == 200
    assert get_res.json()["constraints"]["hours_per_week"] == 25
    assert get_res.json()["constraints"]["career_certainty"] == "committed"
    assert get_res.json()["skill_confidence"]["docker"] == "project-ready"


def test_profile_cross_user_isolation(client: TestClient) -> None:
    """User A's token cannot read or overwrite User B's profile."""
    payload_a = _sample_payload(hours=10, certainty="exploring")
    payload_b = _sample_payload(hours=35, certainty="committed")

    # Authenticate as User A
    app.dependency_overrides[get_current_user] = lambda: USER_A_ID
    post_a = client.post("/api/v1/profile", json=payload_a)
    assert post_a.status_code == 200

    # Switch to User B: cannot see User A's profile
    app.dependency_overrides[get_current_user] = lambda: USER_B_ID
    get_b_initial = client.get("/api/v1/profile")
    assert get_b_initial.status_code == 404

    # User B saves their profile
    post_b = client.post("/api/v1/profile", json=payload_b)
    assert post_b.status_code == 200

    # User B reads their own profile
    get_b = client.get("/api/v1/profile")
    assert get_b.status_code == 200
    assert get_b.json()["constraints"]["hours_per_week"] == 35
    assert get_b.json()["constraints"]["career_certainty"] == "committed"

    # Switch back to User A: User A's profile is intact and unmodified
    app.dependency_overrides[get_current_user] = lambda: USER_A_ID
    get_a = client.get("/api/v1/profile")
    assert get_a.status_code == 200
    assert get_a.json()["constraints"]["hours_per_week"] == 10
    assert get_a.json()["constraints"]["career_certainty"] == "exploring"


def test_profile_invalid_payload_rejected(client: TestClient) -> None:
    """Invalid payload structures (missing questions, invalid constraints) return 422."""
    # Empty payload
    assert client.post("/api/v1/profile", json={}).status_code == 422

    # Incomplete interest responses (fewer than 18)
    incomplete_interests = _sample_payload()
    incomplete_interests["interest_responses"] = {"q1": 5}
    assert client.post("/api/v1/profile", json=incomplete_interests).status_code == 422

    # Invalid certainty value
    bad_certainty = _sample_payload()
    bad_certainty["constraints"]["career_certainty"] = "invalid-value"
    assert client.post("/api/v1/profile", json=bad_certainty).status_code == 422
