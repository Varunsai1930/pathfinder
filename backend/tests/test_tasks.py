"""Tests for authenticated PATCH /tasks/{task_id}."""

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.roadmap_store import _in_memory_roadmaps
from app.task_store import task_ids_for_roadmap_for_test

USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"
ROLE_ID = "frontend-developer"


def _create_task_ids(client: TestClient, user_id: str = USER_A_ID) -> list[str]:
    app.dependency_overrides[get_current_user] = lambda: user_id
    response = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert response.status_code == 200
    roadmap_id = _in_memory_roadmaps[(user_id, ROLE_ID)]["id"]
    return task_ids_for_roadmap_for_test(user_id, roadmap_id)


def test_task_unauthenticated_requests_rejected() -> None:
    app.dependency_overrides.clear()
    response = TestClient(app).patch("/api/v1/tasks/00000000-0000-0000-0000-000000000001", json={"completed": True})
    assert response.status_code in (401, 403)


def test_task_patch_roundtrip_and_next_action_advances(client: TestClient) -> None:
    task_ids = _create_task_ids(client)
    assert len(task_ids) == 5

    for index, task_id in enumerate(task_ids):
        response = client.patch(f"/api/v1/tasks/{task_id}", json={"completed": True})
        assert response.status_code == 200
        body = response.json()
        assert body["task"]["id"] == task_id
        assert body["task"]["completed"] is True
        assert body["task"]["completed_at"] is not None

        if index < 4:
            assert body["next_action"]["milestone_id"] == [
                "frontend-javascript",
                "frontend-react",
                "frontend-quality",
                "frontend-portfolio",
            ][index]
        else:
            assert body["next_action"]["milestone_id"] is None
            assert body["next_action"]["message"] == "All five roadmap milestones are complete. Great work!"

    reopened = client.patch(f"/api/v1/tasks/{task_ids[0]}", json={"completed": False})
    assert reopened.status_code == 200
    assert reopened.json()["task"]["completed"] is False
    assert reopened.json()["task"]["completed_at"] is None
    assert reopened.json()["next_action"]["milestone_id"] == "frontend-web-foundations"


def test_task_cross_user_patch_is_rejected(client: TestClient) -> None:
    task_id = _create_task_ids(client, USER_A_ID)[0]
    app.dependency_overrides[get_current_user] = lambda: USER_B_ID

    response = client.patch(f"/api/v1/tasks/{task_id}", json={"completed": True})
    assert response.status_code == 404

    app.dependency_overrides[get_current_user] = lambda: USER_A_ID
    own_task = client.patch(f"/api/v1/tasks/{task_id}", json={"completed": True})
    assert own_task.status_code == 200


def test_task_patch_validates_body(client: TestClient) -> None:
    task_id = _create_task_ids(client)[0]
    assert client.patch(f"/api/v1/tasks/{task_id}", json={}).status_code == 422
