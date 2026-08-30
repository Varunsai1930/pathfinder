"""Q&A endpoint tests: conversational branch plus the grounded guardrail."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import personalization
from app.config import Settings, get_settings
from app.main import app


def _sample_profile_payload() -> dict:
    return {
        "interest_responses": {
            "realistic-1": 5, "realistic-2": 4, "realistic-3": 3,
            "investigative-1": 2, "investigative-2": 1, "investigative-3": 5,
            "artistic-1": 4, "artistic-2": 3, "artistic-3": 2,
            "social-1": 1, "social-2": 5, "social-3": 4,
            "enterprising-1": 3, "enterprising-2": 2, "enterprising-3": 1,
            "conventional-1": 5, "conventional-2": 4, "conventional-3": 3,
        },
        "skill_confidence": {"python": "practised", "git": "project-ready"},
        "work_style_responses": {
            "analytical": 5, "creative": 3, "collaborative": 4,
            "structured": 4, "systems_oriented": 5,
        },
        "constraints": {"hours_per_week": 15, "target_timeline_weeks": 12, "career_certainty": "deciding"},
    }


@pytest.fixture()
def configured_openrouter() -> Settings:
    settings = Settings(openrouter_api_key="test-key")
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


def _post_question(client: TestClient, question: str):
    return client.post("/api/v1/questions", json={"question": question})


def test_conversational_thanks_gets_brief_reply(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    response = _post_question(client, "Thanks for helping")

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "conversational"
    assert "You're welcome" in body["answer"]
    lowered = body["answer"].lower()
    assert "fit score" not in lowered
    assert "top result" not in lowered


def test_conversational_greetings_and_acknowledgements(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    for message in ("hello", "hey there", "ok got it", "see you later"):
        response = _post_question(client, message)
        assert response.status_code == 200
        assert response.json()["generation_mode"] == "conversational", message


def test_conversational_branch_never_calls_the_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("LLM invoked for conversational input")

    monkeypatch.setattr(personalization, "_structured_completion", _boom)

    response = _post_question(client, "Thanks for helping")

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "conversational"


def test_real_question_stays_grounded(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    response = _post_question(client, "What is my top match?")

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "fallback"
    assert "fit score" in body["answer"].lower()


def test_mixed_thanks_and_question_stays_grounded(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    response = _post_question(client, "Thanks! What is my next milestone?")

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "fallback"


def test_question_mark_disqualifies_conversational_branch(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    response = _post_question(client, "thanks?")

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "fallback"


def test_question_unauthenticated_rejected() -> None:
    app.dependency_overrides.clear()
    raw_client = TestClient(app)

    response = raw_client.post("/api/v1/questions", json={"question": "Thanks for helping"})

    assert response.status_code in (401, 403)


STATED_GOAL = (
    "I'm a second-year student who enjoys building small web pages; I want a "
    "job-ready frontend path in six months with about 10 hours a week."
)


def _post_profile_with_goal(client: TestClient) -> None:
    payload = _sample_profile_payload()
    payload["goal_text"] = STATED_GOAL
    client.post("/api/v1/profile", json=payload)


def test_chatbot_quotes_stated_goal_from_intake(client: TestClient) -> None:
    _post_profile_with_goal(client)

    response = _post_question(client, "What did I write as my goal?")

    assert response.status_code == 200
    body = response.json()
    assert "job-ready frontend path" in body["answer"]
    assert STATED_GOAL in body["answer"]


def test_stated_goal_reaches_the_llm_context(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    _post_profile_with_goal(client)

    captured: dict[str, str] = {}

    def _capture(*args: object, **kwargs: object) -> None:
        captured["user"] = kwargs.get("user", "")
        return None

    monkeypatch.setattr(personalization, "_structured_completion", _capture)

    response = _post_question(client, "What did I write as my goal?")

    assert response.status_code == 200
    assert "stated_goal" in captured["user"]
    assert "job-ready frontend path" in captured["user"]


def test_goal_question_without_stored_goal_degrades_cleanly(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_profile_payload())

    response = _post_question(client, "What did I write as my goal?")

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "fallback"
    assert "stated goal" not in body["answer"].lower()


def test_goal_is_preserved_when_profile_resubmitted_without_it(client: TestClient) -> None:
    _post_profile_with_goal(client)

    resubmitted = _sample_profile_payload()
    resubmitted["constraints"]["hours_per_week"] = 20
    client.post("/api/v1/profile", json=resubmitted)

    stored = client.get("/api/v1/profile")
    assert stored.status_code == 200
    assert stored.json()["goal_text"] == STATED_GOAL

    answer = _post_question(client, "What is my stated objective?")
    assert answer.status_code == 200
    assert STATED_GOAL in answer.json()["answer"]
