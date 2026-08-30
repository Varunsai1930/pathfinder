"""Regression tests for the roadmap display-layer memo.

Before the memo, every GET /roadmaps for a roadmap with any completed
milestone re-ran the OpenRouter personalization (25s timeout) and never
persisted the result — a repeat Progress/Dashboard load paid the LLM again
for byte-identical input.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import roadmap_store

ROLE_ID = "frontend-developer"

PROFILE = {
    "interest_responses": {f"q{i}": 3 for i in range(1, 19)},
    "skill_confidence": {"git": "aware"},
    "work_style_responses": {
        "analytical": 3, "creative": 3, "collaborative": 3,
        "structured": 3, "systems_oriented": 3,
    },
    "constraints": {"hours_per_week": 10, "target_timeline_weeks": 24, "career_certainty": "exploring"},
}


@pytest.fixture()
def personalization_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count personalize_roadmap_response invocations behind the API."""
    calls = {"n": 0}
    real = roadmap_store.personalize_roadmap_response

    def counting(*args: object, **kwargs: object):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(roadmap_store, "personalize_roadmap_response", counting)
    return calls


def _create_roadmap_with_progress(client: TestClient, personalization_calls: dict[str, int]) -> None:
    assert client.post("/api/v1/profile", json=PROFILE).status_code == 200
    created = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert created.status_code == 200
    task_id = created.json()["weekly_plan"][0]["task_id"]
    assert client.patch(f"/api/v1/tasks/{task_id}", json={"completed": True}).status_code == 200
    personalization_calls["n"] = 0  # creation/patch bookkeeping is not under test


def test_repeat_get_with_unchanged_progress_serves_cached_layer(
    client: TestClient, personalization_calls: dict[str, int]
) -> None:
    _create_roadmap_with_progress(client, personalization_calls)

    first = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert first.status_code == 200
    after_first = personalization_calls["n"]
    assert after_first == 1  # state changed since the memo was seeded: one recompute

    second = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert second.status_code == 200
    assert personalization_calls["n"] == after_first  # memo hit: no recompute
    assert second.json() == first.json()


def test_task_state_change_recomputes_display_layer(
    client: TestClient, personalization_calls: dict[str, int]
) -> None:
    _create_roadmap_with_progress(client, personalization_calls)
    client.get(f"/api/v1/roadmaps/{ROLE_ID}")  # warm the memo
    warmed = personalization_calls["n"]

    task_id = client.get(f"/api/v1/roadmaps/{ROLE_ID}").json()["weekly_plan"][1]["task_id"]
    assert client.patch(f"/api/v1/tasks/{task_id}", json={"completed": True}).status_code == 200

    client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert personalization_calls["n"] == warmed + 1  # new state: honest recompute


def test_profile_resubmission_invalidates_cached_layer(
    client: TestClient, personalization_calls: dict[str, int]
) -> None:
    _create_roadmap_with_progress(client, personalization_calls)
    client.get(f"/api/v1/roadmaps/{ROLE_ID}")  # warm the memo
    warmed = personalization_calls["n"]

    # Same task state, but the profile changed — the layer must re-personalize.
    assert client.post("/api/v1/profile", json=PROFILE).status_code == 200
    client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert personalization_calls["n"] == warmed + 1
