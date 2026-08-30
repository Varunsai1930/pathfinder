"""Tests for authenticated PATCH /tasks/{task_id}."""

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.roadmap_store import _in_memory_roadmaps
from app.task_store import _in_memory_tasks, _milestone_sequence

USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"
ROLE_ID = "frontend-developer"


def task_ids_for_roadmap_for_test(user_id: str, roadmap_id: str) -> list[str]:
    """Ordered local task IDs — moved here from app.task_store (test-only)."""
    return [
        task_id
        for task_id, row in sorted(
            _in_memory_tasks.items(), key=lambda item: _milestone_sequence(item[1]["milestone_id"])
        )
        if row["user_id"] == user_id and row["roadmap_id"] == roadmap_id
    ]


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


def test_task_patch_persists_telemetry_both_fields_set(client: TestClient) -> None:
    task_ids = _create_task_ids(client)

    response = client.patch(
        f"/api/v1/tasks/{task_ids[0]}",
        json={"completed": True, "time_spent_minutes": 45, "quiz_score": 40},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["task"]["time_spent_minutes"] == 45
    assert body["task"]["quiz_score"] == 40
    assert body["task"]["completed"] is True

    summary = body["telemetry_summary"]
    assert summary["completed_count"] == 1
    assert summary["total_count"] == 5
    assert summary["completion_rate"] == 20.0
    assert summary["avg_time_spent_minutes"] == 45.0
    assert summary["avg_quiz_score"] == 40.0
    assert summary["pace_note"].startswith("Fast pace")

    # Low quiz average steers the next-action hint toward review.
    assert "review fundamentals before advancing" in body["next_action"]["message"]

    # A second completed milestone without telemetry leaves averages on the
    # tasks that did report values.
    second = client.patch(f"/api/v1/tasks/{task_ids[1]}", json={"completed": True})
    assert second.status_code == 200
    second_summary = second.json()["telemetry_summary"]
    assert second_summary["completed_count"] == 2
    assert second_summary["avg_time_spent_minutes"] == 45.0
    assert second_summary["avg_quiz_score"] == 40.0

    # The roadmap read path surfaces telemetry on the weekly plan items.
    roadmap = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert roadmap.status_code == 200
    first_week = next(
        item for item in roadmap.json()["weekly_plan"] if item["task_id"] == task_ids[0]
    )
    assert first_week["completed"] is True
    assert first_week["time_spent_minutes"] == 45
    assert first_week["quiz_score"] == 40


def test_task_patch_without_telemetry_keeps_fields_absent(client: TestClient) -> None:
    task_ids = _create_task_ids(client)

    response = client.patch(f"/api/v1/tasks/{task_ids[0]}", json={"completed": True})
    assert response.status_code == 200
    body = response.json()
    assert body["task"]["completed"] is True
    assert body["task"]["time_spent_minutes"] is None
    assert body["task"]["quiz_score"] is None

    summary = body["telemetry_summary"]
    assert summary["completed_count"] == 1
    assert summary["avg_time_spent_minutes"] is None
    assert summary["avg_quiz_score"] is None
    assert summary["pace_note"] == ""

    # No telemetry means no adaptive suffix on the next-action message.
    assert body["next_action"]["message"] == "Next: Interactive JavaScript"


def test_task_patch_telemetry_range_validation(client: TestClient) -> None:
    task_id = _create_task_ids(client)[0]

    for payload in (
        {"completed": True, "time_spent_minutes": 10081},
        {"completed": True, "time_spent_minutes": -1},
        {"completed": True, "quiz_score": 101},
        {"completed": True, "quiz_score": -5},
    ):
        assert client.patch(f"/api/v1/tasks/{task_id}", json=payload).status_code == 422

    for payload in (
        {"completed": True, "time_spent_minutes": 0, "quiz_score": 0},
        {"completed": True, "time_spent_minutes": 10080, "quiz_score": 100},
    ):
        accepted = client.patch(f"/api/v1/tasks/{task_id}", json=payload)
        assert accepted.status_code == 200
        assert accepted.json()["task"]["completed"] is True
