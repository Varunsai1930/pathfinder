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
    assert len(recs) == 4
    
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

def test_match_unauthenticated_rejected() -> None:
    app.dependency_overrides.clear()
    raw_client = TestClient(app)
    response = raw_client.post("/api/v1/match")
    assert response.status_code in (401, 403)

def test_match_no_profile_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/match")
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()
