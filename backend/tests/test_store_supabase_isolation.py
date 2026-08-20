"""Regression tests: Supabase-mode writes must never mirror into in-memory stores.

A long-running Railway process would grow without bound if every production
write also landed in the module-level fallback dicts.
"""

import httpx

from app.config import Settings
from app.matching.models import ProfilePayload
from app.profile_store import _in_memory_profiles, reset_in_memory_store, upsert_profile
from app.roadmap_store import (
    _in_memory_roadmaps,
    reset_in_memory_roadmap_store,
    upsert_roadmap,
)
from app.task_store import _in_memory_tasks, reset_in_memory_task_store

USER_ID = "33333333-3333-3333-3333-333333333333"

SAMPLE_PROFILE = {
    "interest_responses": {f"q{i}": (i % 5) + 1 for i in range(1, 19)},
    "skill_confidence": {"python": "practised", "git": "aware"},
    "work_style_responses": {
        "analytical": 5,
        "creative": 3,
        "collaborative": 4,
        "structured": 4,
        "systems_oriented": 5,
    },
    "constraints": {"hours_per_week": 10, "target_timeline_weeks": 12, "career_certainty": "deciding"},
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = "fake response"
        self.content = b"[]"

    def json(self) -> object:
        return self._payload


class _FakePostgrestClient:
    """Stand-in for httpx.Client that records requests and echoes upserted rows."""

    calls: list[str] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "_FakePostgrestClient":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def post(self, url: str, headers: dict | None = None, json: object = None) -> _FakeResponse:
        type(self).calls.append(f"POST {url}")
        if isinstance(json, dict):
            # PostgREST with return=representation answers with the stored row,
            # including the database-generated id / created_at.
            row = {
                **json,
                "id": "00000000-0000-0000-0000-0000000000ff",
                "created_at": json.get("updated_at", "2026-01-01T00:00:00+00:00"),
            }
            return _FakeResponse(201, [row])
        return _FakeResponse(201, json)

    def get(self, url: str, headers: dict | None = None) -> _FakeResponse:
        type(self).calls.append(f"GET {url}")
        return _FakeResponse(200, [])

    def patch(self, url: str, headers: dict | None = None, json: object = None) -> _FakeResponse:
        type(self).calls.append(f"PATCH {url}")
        return _FakeResponse(200, [json])


def _supabase_settings() -> Settings:
    return Settings(
        supabase_url="https://fake-project.supabase.co",
        supabase_anon_key="test-anon-key",
    )


def _reset_local_stores() -> None:
    reset_in_memory_store()
    reset_in_memory_roadmap_store()
    reset_in_memory_task_store()


def test_profile_supabase_write_does_not_mirror_into_memory(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "Client", _FakePostgrestClient)
    _FakePostgrestClient.calls = []
    _reset_local_stores()

    response = upsert_profile(
        user_id=USER_ID,
        payload=ProfilePayload.model_validate(SAMPLE_PROFILE),
        settings=_supabase_settings(),
    )

    assert response.constraints.hours_per_week == 10
    assert any(call.startswith("POST ") and call.endswith("/rest/v1/profiles") for call in _FakePostgrestClient.calls)
    assert _in_memory_profiles == {}


def test_roadmap_supabase_write_does_not_mirror_into_memory(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "Client", _FakePostgrestClient)
    _FakePostgrestClient.calls = []
    _reset_local_stores()

    roadmap = upsert_roadmap(
        user_id=USER_ID,
        role_id="frontend-developer",
        settings=_supabase_settings(),
    )

    assert roadmap.role_id == "frontend-developer"
    assert len(roadmap.weekly_plan) == 5
    assert any(call.startswith("POST ") and "/rest/v1/roadmaps" in call for call in _FakePostgrestClient.calls)
    assert any(call.startswith("POST ") and "/rest/v1/tasks" in call for call in _FakePostgrestClient.calls)
    assert _in_memory_roadmaps == {}
    assert _in_memory_tasks == {}


def test_fallback_mode_still_persists_in_memory(monkeypatch) -> None:
    """Without Supabase configured, local writes must keep working as before."""
    monkeypatch.setattr(httpx, "Client", _FakePostgrestClient)
    _FakePostgrestClient.calls = []
    _reset_local_stores()

    upsert_profile(
        user_id=USER_ID,
        payload=ProfilePayload.model_validate(SAMPLE_PROFILE),
        settings=Settings(),
    )
    upsert_roadmap(user_id=USER_ID, role_id="frontend-developer", settings=Settings())

    assert USER_ID in _in_memory_profiles
    assert (USER_ID, "frontend-developer") in _in_memory_roadmaps
    assert len(_in_memory_tasks) == 5
    assert _FakePostgrestClient.calls == []
