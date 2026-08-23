import pytest
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.main import app

def _sample_payload() -> dict:
    return {
        "interest_responses": {
            "realistic-1": 5, "realistic-2": 4, "realistic-3": 3,
            "investigative-1": 2, "investigative-2": 1, "investigative-3": 5,
            "artistic-1": 4, "artistic-2": 3, "artistic-3": 2,
            "social-1": 1, "social-2": 5, "social-3": 4,
            "enterprising-1": 3, "enterprising-2": 2, "enterprising-3": 1,
            "conventional-1": 5, "conventional-2": 4, "conventional-3": 3,
        },
        "skill_confidence": {
            "python": "practised",
            "javascript": "project-ready",
            "sql": "aware",
            "git": "project-ready",
        },
        "work_style_responses": {
            "analytical": 5, "creative": 3, "collaborative": 4,
            "structured": 4, "systems_oriented": 5,
        },
        "constraints": {
            "hours_per_week": 15,
            "target_timeline_weeks": 12,
            "career_certainty": "deciding",
        },
    }

def test_match_authenticated_roundtrip(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_payload())
    response = client.post("/api/v1/match")
    
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    
    recs = data["recommendations"]
    assert len(recs) == 6
    
    for rank, rec in enumerate(recs, start=1):
        assert rec["rank"] == rank
        assert "role_id" in rec
        assert "role_title" in rec
        assert "pathfinder_fit_score" in rec
        assert 0 <= rec["pathfinder_fit_score"] <= 100
        
        breakdown = rec["score_breakdown"]
        assert "interest_alignment" in breakdown
        assert "skill_readiness" in breakdown
        assert "work_style_alignment" in breakdown

        confirmed = set(rec["confirmed_skills"])
        missing_core = set(rec["missing_core_skills"])
        missing_supporting = set(rec["missing_supporting_skills"])
        missing_all = missing_core | missing_supporting

        assert not (confirmed & missing_all), (
            f"Role {rec['role_id']} has overlap between confirmed and missing: {confirmed & missing_all}"
        )


def test_match_skills_have_zero_overlap_all_roles(client: TestClient) -> None:
    """Zero overlap between confirmed_skills and missing skills across all 4 roles."""
    payload = _sample_payload()
    payload["skill_confidence"] = {
        "html-css": "practised",
        "javascript": "project-ready",
        "react": "aware",
        "python": "practised",
        "api-design": "none",
        "sql": "aware",
        "git": "project-ready",
        "linux": "practised",
        "cloud-basics": "aware",
        "containers": "none",
    }
    client.post("/api/v1/profile", json=payload)
    response = client.post("/api/v1/match")

    assert response.status_code == 200
    recs = response.json()["recommendations"]
    assert len(recs) == 6

    for rec in recs:
        confirmed = set(rec["confirmed_skills"])
        missing_core = set(rec["missing_core_skills"])
        missing_supporting = set(rec["missing_supporting_skills"])
        missing_all = missing_core | missing_supporting

        # Zero overlap
        assert not (confirmed & missing_all), (
            f"Role '{rec['role_id']}' overlap: {confirmed & missing_all}"
        )

        # Confirmed skills must strictly be practised or project-ready
        for skill_name in confirmed:
            assert skill_name not in missing_all


def test_match_unauthenticated_rejected() -> None:
    app.dependency_overrides.clear()
    raw_client = TestClient(app)
    response = raw_client.post("/api/v1/match")
    assert response.status_code in (401, 403)


def test_match_no_profile_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/match")
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


def test_match_get_404_without_profile(client: TestClient) -> None:
    response = client.get("/api/v1/match")
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


def test_match_get_404_when_never_computed(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_payload())

    response = client.get("/api/v1/match")

    assert response.status_code == 404


def test_match_get_serves_persisted_result_without_recompute(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/api/v1/profile", json=_sample_payload())
    computed = client.post("/api/v1/match")
    assert computed.status_code == 200

    # Any recompute attempt fails loudly, proving GET serves the persisted result.
    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("match recomputed on GET")

    monkeypatch.setattr("app.api.match_profile", _boom)

    response = client.get("/api/v1/match")

    assert response.status_code == 200
    assert response.json() == computed.json()


def test_match_result_stale_after_profile_resubmission(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_payload())
    client.post("/api/v1/match")
    assert client.get("/api/v1/match").status_code == 200

    resubmitted = _sample_payload()
    resubmitted["constraints"]["hours_per_week"] = 20
    client.post("/api/v1/profile", json=resubmitted)

    # Profile version changed: the old result must no longer be served.
    assert client.get("/api/v1/match").status_code == 404

    recomputed = client.post("/api/v1/match")
    assert recomputed.status_code == 200
    assert client.get("/api/v1/match").status_code == 200
    assert client.get("/api/v1/match").json() == recomputed.json()

