from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_catalog_endpoint_returns_all_roles() -> None:
    response = TestClient(app).get("/api/v1/catalog/roles")

    assert response.status_code == 200
    assert len(response.json()["roles"]) == 4


def test_assessment_endpoint_returns_a_balanced_question_set() -> None:
    response = TestClient(app).get("/api/v1/assessment")

    assert response.status_code == 200
    assert len(response.json()["interest_questions"]) == 18
    assert len(response.json()["skills"]) == 19
