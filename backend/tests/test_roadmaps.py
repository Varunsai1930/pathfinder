"""Tests for authenticated roadmap creation and retrieval."""

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app

USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"
ROLE_ID = "frontend-developer"


def test_roadmap_unauthenticated_requests_rejected() -> None:
    app.dependency_overrides.clear()
    raw_client = TestClient(app)

    assert raw_client.post(f"/api/v1/roadmaps/{ROLE_ID}").status_code in (401, 403)
    assert raw_client.get(f"/api/v1/roadmaps/{ROLE_ID}").status_code in (401, 403)


def test_roadmap_authenticated_roundtrip(client: TestClient) -> None:
    created = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert created.status_code == 200
    data = created.json()
    assert data["role_id"] == ROLE_ID
    assert data["generation_mode"] == "fallback"
    assert [item["week"] for item in data["weekly_plan"]] == [1, 2, 3, 4, 5]
    assert [item["milestone_id"] for item in data["weekly_plan"]] == [
        "frontend-web-foundations",
        "frontend-javascript",
        "frontend-react",
        "frontend-quality",
        "frontend-portfolio",
    ]
    assert all(item["task_id"] is not None for item in data["weekly_plan"])
    assert all(item["completed"] is False for item in data["weekly_plan"])

    fetched = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert fetched.status_code == 200
    assert fetched.json() == data

    completed_task_id = data["weekly_plan"][0]["task_id"]
    task_update = client.patch(f"/api/v1/tasks/{completed_task_id}", json={"completed": True})
    assert task_update.status_code == 200

    fetched_after_update = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert fetched_after_update.status_code == 200
    assert fetched_after_update.json()["weekly_plan"][0]["task_id"] == completed_task_id
    assert fetched_after_update.json()["weekly_plan"][0]["completed"] is True

    root_fetched = client.get(f"/roadmaps/{ROLE_ID}")
    assert root_fetched.status_code == 200
    assert root_fetched.json() == fetched_after_update.json()


def test_roadmap_not_found_returns_clean_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_roadmap_invalid_role_id_is_rejected(client: TestClient) -> None:
    for method in (client.post, client.get):
        response = method("/api/v1/roadmaps/not-a-real-role")
        assert response.status_code == 404
        assert "unknown role_id" in response.json()["detail"].lower()


def test_roadmap_cross_user_isolation(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: USER_A_ID
    assert client.post(f"/api/v1/roadmaps/{ROLE_ID}").status_code == 200

    app.dependency_overrides[get_current_user] = lambda: USER_B_ID
    assert client.get(f"/api/v1/roadmaps/{ROLE_ID}").status_code == 404

    user_b_created = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert user_b_created.status_code == 200

    app.dependency_overrides[get_current_user] = lambda: USER_A_ID
    user_a_fetched = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert user_a_fetched.status_code == 200
    assert user_a_fetched.json()["role_id"] == ROLE_ID
