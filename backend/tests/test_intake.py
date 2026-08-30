"""Conversational goal-intake tests: LLM extraction, deterministic mapping, fallbacks."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import personalization
from app.catalog.assessment_loader import get_assessment_catalog
from app.config import Settings, get_settings
from app.main import app

GOAL_TEXT = (
    "I'm a second-year student who enjoys building small web pages and digging "
    "through spreadsheet data. I can study about 10 hours a week and want to be "
    "job-ready in roughly six months, but I'm still comparing directions."
)


def _valid_extraction() -> dict[str, Any]:
    return {
        "goal_summary": (
            "A second-year student who enjoys building web pages and exploring "
            "spreadsheet data, comparing directions with about 10 weekly hours "
            "and a six-month target."
        ),
        "riasec_hints": {
            "realistic": 25,
            "investigative": 75,
            "artistic": 50,
            "social": 50,
            "enterprising": 25,
            "conventional": 75,
        },
        "skill_hints": [
            {"skill_id": "html-css", "confidence": "practised"},
            {"skill_id": "spreadsheets", "confidence": "aware"},
        ],
        "hours_per_week_hint": 10,
        "timeline_weeks_hint": 24,
        "career_certainty_hint": "deciding",
        "supported_path": "frontend-developer",
    }


def _mock_openrouter(monkeypatch: pytest.MonkeyPatch, result: str | BaseException) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            captured["request"] = kwargs
            if isinstance(result, BaseException):
                raise result
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=result))])

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(personalization, "OpenAI", FakeOpenAI)
    return captured


@pytest.fixture()
def configured_openrouter() -> Settings:
    settings = Settings(openrouter_api_key="test-key")
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


def test_intake_without_api_key_returns_neutral_fallback(client: TestClient) -> None:
    response = client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "fallback"
    assert body["goal_summary"] == ""
    assert body["interest_suggestions"] == {}
    assert body["skill_suggestions"] == {}
    assert body["hours_per_week_suggestion"] is None
    assert body["timeline_weeks_suggestion"] is None
    assert body["career_certainty_suggestion"] is None


def test_intake_llm_path_maps_dimension_hints_to_every_question(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    _mock_openrouter(monkeypatch, json.dumps(_valid_extraction()))

    response = client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "llm"
    assert body["goal_summary"]

    assessment = get_assessment_catalog()
    expected_ids = {question.id for question in assessment.interest_questions}
    assert set(body["interest_suggestions"]) == expected_ids
    assert all(1 <= value <= 5 for value in body["interest_suggestions"].values())

    by_dimension = {question.id: question.dimension.value for question in assessment.interest_questions}
    for question_id, suggestion in body["interest_suggestions"].items():
        hint = _valid_extraction()["riasec_hints"][by_dimension[question_id]]
        assert suggestion == 1 + round(hint / 25)

    assert body["skill_suggestions"] == {"html-css": "practised", "spreadsheets": "aware"}
    assert body["hours_per_week_suggestion"] == 10
    assert body["timeline_weeks_suggestion"] == 24
    assert body["career_certainty_suggestion"] == "deciding"


def test_intake_drops_unknown_skill_ids_but_keeps_valid_ones(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    extraction = _valid_extraction()
    extraction["skill_hints"] = [
        {"skill_id": "quantum-computing", "confidence": "project-ready"},
        {"skill_id": "git", "confidence": "aware"},
    ]
    _mock_openrouter(monkeypatch, json.dumps(extraction))

    response = client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "llm"
    assert body["skill_suggestions"] == {"git": "aware"}


def test_intake_declines_goal_outside_supported_paths(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """Unsupported goals get no draft and no derived hints — decline, don't force-fit."""
    extraction = _valid_extraction()
    extraction["supported_path"] = "none"
    _mock_openrouter(monkeypatch, json.dumps(extraction))

    response = client.post(
        "/api/v1/intake",
        json={"goal_text": "I want to become a professional chef and open a bakery."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "fallback"
    assert body["decline_reason"] == "unsupported_goal"
    assert body["interest_suggestions"] == {}
    assert body["skill_suggestions"] == {}
    assert body["hours_per_week_suggestion"] is None
    assert body["timeline_weeks_suggestion"] is None
    assert body["career_certainty_suggestion"] is None


def test_intake_supported_goal_has_no_decline_reason(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    _mock_openrouter(monkeypatch, json.dumps(_valid_extraction()))

    response = client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "llm"
    assert body["decline_reason"] == ""
    assert body["interest_suggestions"] != {}


def test_intake_invalid_supported_path_rejected_by_schema(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """A classification outside the six supported paths + none is a schema failure:
    the generic unavailable fallback applies, never a false decline claim."""
    extraction = _valid_extraction()
    extraction["supported_path"] = "nurse"
    _mock_openrouter(monkeypatch, json.dumps(extraction))

    response = client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "fallback"
    assert body["decline_reason"] == ""


def test_intake_schema_failure_returns_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    _mock_openrouter(monkeypatch, "not json at all")

    response = client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "fallback"
    assert body["interest_suggestions"] == {}


def test_intake_rejects_too_short_goal_text(client: TestClient) -> None:
    response = client.post("/api/v1/intake", json={"goal_text": "too short"})

    assert response.status_code == 422


def test_intake_unauthenticated_request_rejected() -> None:
    app.dependency_overrides.clear()
    raw_client = TestClient(app)

    response = raw_client.post("/api/v1/intake", json={"goal_text": GOAL_TEXT})

    assert response.status_code in (401, 403)
