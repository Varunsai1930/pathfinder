import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROLES_PATH = Path(__file__).resolve().parent.parent / "app" / "catalog" / "roles.v1.json"
ASSESSMENT_PATH = Path(__file__).resolve().parent.parent / "app" / "catalog" / "assessment.v1.json"


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_catalog_endpoint_unauthenticated_matches_json() -> None:
    """Unauthenticated client can fetch full roles catalog matching source JSON."""
    raw_client = TestClient(app)
    response = raw_client.get("/api/v1/catalog/roles")

    assert response.status_code == 200
    with ROLES_PATH.open("r", encoding="utf-8") as f:
        expected = json.load(f)
    assert response.json() == expected


def test_assessment_catalog_endpoint_unauthenticated_matches_json() -> None:
    """Unauthenticated client can fetch assessment catalog matching source JSON."""
    raw_client = TestClient(app)
    response = raw_client.get("/api/v1/catalog/assessment")

    assert response.status_code == 200
    with ASSESSMENT_PATH.open("r", encoding="utf-8") as f:
        expected = json.load(f)
    assert response.json() == expected



def test_match_endpoint_rejects_unauthenticated_requests() -> None:
    """Protected endpoints require Authorization header."""
    app.dependency_overrides.clear()
    raw_client = TestClient(app)
    response = raw_client.post("/api/v1/match")

    assert response.status_code in (401, 403)
