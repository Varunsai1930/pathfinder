"""OpenRouter roadmap-personalization tests with deterministic fallbacks."""

from __future__ import annotations

import json
import os
from datetime import UTC
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import personalization
from app.config import Settings, get_settings
from app.main import app
from app.matching.models import CareerRecommendation, ProfileConstraints, ScoreBreakdown
from app.roadmap_models import RoadmapResponse
from app.roadmap_store import _weekly_plan_for

ROLE_ID = "frontend-developer"
FOCUS_TEXT = "With your 15 weekly hours and solid HTML basics, this milestone should feel familiar."


def _sample_payload() -> dict[str, Any]:
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
            "python": "practised", "javascript": "project-ready", "sql": "aware", "git": "project-ready"
        },
        "work_style_responses": {
            "analytical": 5, "creative": 3, "collaborative": 4, "structured": 4, "systems_oriented": 5
        },
        "constraints": {"hours_per_week": 15, "target_timeline_weeks": 12, "career_certainty": "deciding"},
    }


def _valid_openrouter_payload(completed_count: int = 0) -> dict[str, Any]:
    milestones = _weekly_plan_for(ROLE_ID)
    return {
        "fit_explanation": (
            "This role reflects the supplied score breakdown. "
            "Address the listed core skill gaps through the fixed weekly milestones."
        ),
        "adaptation_note": (
            f"You have completed {completed_count} of 5 milestones; next up is Week {completed_count + 1}."
            if completed_count
            else ""
        ),
        "weekly_focus": [
            {"milestone_id": item.milestone_id, "personalized_focus": FOCUS_TEXT}
            for item in milestones
        ],
    }


def _mock_openrouter(monkeypatch: pytest.MonkeyPatch, result: str | BaseException) -> dict[str, Any]:
    """Mock the OpenAI SDK transport used for OpenRouter's compatible API."""
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


def _create_profile_and_roadmap(client: TestClient) -> Any:
    assert client.post("/api/v1/profile", json=_sample_payload()).status_code == 200
    return client.post(f"/api/v1/roadmaps/{ROLE_ID}")


def _recommendation() -> CareerRecommendation:
    return CareerRecommendation(
        rank=1,
        role_id=ROLE_ID,
        role_title="Frontend Developer",
        pathfinder_fit_score=82.5,
        score_breakdown=ScoreBreakdown(interest_alignment=90, skill_readiness=71, work_style_alignment=84),
        confirmed_skills=["javascript", "html-css", "git"],
        missing_core_skills=["react", "testing"],
        missing_supporting_skills=["accessibility"],
    )


def _roadmap(completed: int = 0) -> RoadmapResponse:
    from datetime import datetime

    now = datetime.now(UTC)
    weekly_plan = _weekly_plan_for(ROLE_ID)
    for item in weekly_plan[:completed]:
        item.completed = True
    return RoadmapResponse(
        role_id=ROLE_ID, weekly_plan=weekly_plan, generation_mode="fallback",
        created_at=now, updated_at=now,
    )


def _constraints() -> ProfileConstraints:
    return ProfileConstraints(hours_per_week=15, target_timeline_weeks=12, career_certainty="deciding")


def _weak_constraints() -> ProfileConstraints:
    return ProfileConstraints(hours_per_week=3, target_timeline_weeks=12, career_certainty="exploring")


def _weak_recommendation() -> CareerRecommendation:
    """The synthetic weak-fit learner: low score and zero confirmed skills."""
    return CareerRecommendation(
        rank=1,
        role_id=ROLE_ID,
        role_title="Frontend Developer",
        pathfinder_fit_score=36.0,
        score_breakdown=ScoreBreakdown(interest_alignment=30, skill_readiness=25, work_style_alignment=60),
        confirmed_skills=[],
        missing_core_skills=["javascript", "html-css"],
        missing_supporting_skills=[],
    )


def _python_only_recommendation() -> CareerRecommendation:
    """Synthetic partial-profile learner used to exercise skill-fabrication guards."""
    return _recommendation().model_copy(
        update={
            "confirmed_skills": ["python"],
            "missing_core_skills": ["javascript", "html-css", "react"],
        }
    )


def _payload_with_texts(fit_text: str, focus_text: str) -> dict[str, Any]:
    milestones = _weekly_plan_for(ROLE_ID)
    return {
        "fit_explanation": fit_text,
        "adaptation_note": "",
        "weekly_focus": [
            {"milestone_id": item.milestone_id, "personalized_focus": focus_text}
            for item in milestones
        ],
    }


def test_successful_openrouter_path_uses_expected_client_and_returns_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    captured = _mock_openrouter(monkeypatch, json.dumps(_valid_openrouter_payload()))

    response = _create_profile_and_roadmap(client)

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "llm"
    assert body["fit_explanation"]
    assert body["adaptation_note"] == ""  # zero completions at creation time
    assert all(item["personalized_focus"] == FOCUS_TEXT for item in body["weekly_plan"])
    assert captured["client"] == {
        "api_key": "test-key",
        "base_url": "https://openrouter.ai/api/v1",
        "timeout": 25.0,
        "max_retries": 0,
    }
    assert captured["request"]["model"] == configured_openrouter.openrouter_model
    assert captured["request"]["response_format"]["type"] == "json_schema"


def test_prompt_context_carries_completion_state_and_learner_facts(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    captured = _mock_openrouter(monkeypatch, json.dumps(_valid_openrouter_payload(completed_count=2)))

    result = personalization.personalize_roadmap_response(
        _roadmap(completed=2), _recommendation(), _constraints(), configured_openrouter
    )

    context = json.loads(captured["request"]["messages"][1]["content"])
    assert context["progress"]["completed_task_count"] == 2
    assert len(context["progress"]["completed_milestone_ids"]) == 2
    assert context["progress"]["next_milestone_id"] == "frontend-react"
    assert context["learner"]["hours_per_week"] == 15
    assert context["learner"]["strongest_skills"] == ["javascript", "html-css", "git"]
    assert context["learner"]["missing_core_skills"] == ["react", "testing"]
    assert [m["completed"] for m in context["milestones"]] == [True, True, False, False, False]
    assert "DO NOT repeat the milestone title or objective verbatim" in captured["request"]["messages"][0]["content"]
    assert result.generation_mode == "llm"
    assert result.adaptation_note


def test_adaptation_note_contract_enforced_regardless_of_model_output(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    # Model returned an empty note despite 2 completed milestones:
    # a specific deterministic note must be substituted, not an empty string.
    empty_note = _valid_openrouter_payload(completed_count=2)
    empty_note["adaptation_note"] = ""
    _mock_openrouter(monkeypatch, json.dumps(empty_note))

    with_progress = personalization.personalize_roadmap_response(
        _roadmap(completed=2), _recommendation(), _constraints(), configured_openrouter
    )
    assert with_progress.adaptation_note
    assert "2 of 5" in with_progress.adaptation_note
    assert with_progress.generation_mode == "llm"

    # Model invented a note at zero completions: it must be forced empty.
    premature_note = _valid_openrouter_payload()
    premature_note["adaptation_note"] = "You have completed 1 of 5 milestones so far."
    _mock_openrouter(monkeypatch, json.dumps(premature_note))

    fresh = personalization.personalize_roadmap_response(
        _roadmap(), _recommendation(), _constraints(), configured_openrouter
    )
    assert fresh.adaptation_note == ""


def test_catalog_fields_never_change_under_llm_output(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    _mock_openrouter(monkeypatch, json.dumps(_valid_openrouter_payload()))

    base = _roadmap(completed=1)
    result = personalization.personalize_roadmap_response(
        base, _recommendation(), _constraints(), configured_openrouter
    )

    for original, personalized_item in zip(base.weekly_plan, result.weekly_plan, strict=False):
        assert personalized_item.title == original.title
        assert personalized_item.objective == original.objective
        assert personalized_item.skills == original.skills
        assert personalized_item.resources == original.resources
        assert personalized_item.estimated_effort_hours == original.estimated_effort_hours
        assert personalized_item.completed == original.completed
        assert personalized_item.personalized_focus == FOCUS_TEXT


@pytest.mark.parametrize(
    ("provider_result", "mutate"),
    [
        ("not valid JSON", None),
        (None, "unknown_milestone"),
        (TimeoutError("provider timed out"), None),
    ],
)
def test_invalid_or_unavailable_openrouter_output_falls_back_without_dashboard_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    configured_openrouter: Settings,
    provider_result: str | BaseException | None,
    mutate: str | None,
) -> None:
    if mutate == "unknown_milestone":
        payload = _valid_openrouter_payload()
        payload["weekly_focus"][0]["milestone_id"] = "not-a-real-milestone"
        provider_result = json.dumps(payload)
    assert provider_result is not None
    _mock_openrouter(monkeypatch, provider_result)

    response = _create_profile_and_roadmap(client)

    # The dashboard's POST source is always a valid roadmap response.
    assert response.status_code == 200
    assert response.json()["generation_mode"] == "fallback"
    assert response.json()["weekly_plan"][0]["milestone_id"] == "frontend-web-foundations"
    assert all(item["personalized_focus"] for item in response.json()["weekly_plan"])
    assert response.json()["adaptation_note"] == ""  # zero completions at creation


def test_get_roadmap_repersonalizes_pacing_after_progress(
    client: TestClient,
) -> None:
    """Completion state must reach the adaptation note on GET, not just creation."""
    assert client.post("/api/v1/profile", json=_sample_payload()).status_code == 200
    created = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert created.status_code == 200

    fetched = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    assert fetched.json()["adaptation_note"] == ""  # fresh roadmap: genuinely zero completions

    for item in fetched.json()["weekly_plan"][:2]:
        assert client.patch(f"/api/v1/tasks/{item['task_id']}", json={"completed": True}).status_code == 200

    with_progress = client.get(f"/api/v1/roadmaps/{ROLE_ID}")
    note = with_progress.json()["adaptation_note"]
    assert note  # deterministic fallback note in tests (no OpenRouter key configured)
    assert "2 of 5" in note
    assert all(item["personalized_focus"] for item in with_progress.json()["weekly_plan"])


def test_no_key_remains_deterministic(client: TestClient) -> None:
    response = _create_profile_and_roadmap(client)

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "fallback"
    assert all(item["personalized_focus"] for item in response.json()["weekly_plan"])
    assert response.json()["adaptation_note"] == ""  # zero completions at creation


def test_verbatim_title_objective_is_replaced(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """If model lazily outputs '{title}: {objective}', personalized pacing replaces it."""
    milestones = _weekly_plan_for(ROLE_ID)
    lazy_payload = {
        "fit_explanation": (
            "This role reflects the supplied score breakdown. "
            "Address the listed core skill gaps through the fixed weekly milestones."
        ),
        "adaptation_note": "You have completed 1 of 5 milestones; next up is Week 2.",
        "weekly_focus": [
            {"milestone_id": item.milestone_id, "personalized_focus": f"{item.title}: {item.objective}"}
            for item in milestones
        ],
    }
    _mock_openrouter(monkeypatch, json.dumps(lazy_payload))

    result = personalization.personalize_roadmap_response(
        _roadmap(completed=1), _recommendation(), _constraints(), configured_openrouter
    )

    for orig, item in zip(milestones, result.weekly_plan, strict=False):
        verbatim = f"{orig.title}: {orig.objective}"
        assert item.personalized_focus != verbatim
        assert not item.personalized_focus.startswith(f"{orig.title}:")
        assert len(item.personalized_focus) > 20


def test_upsert_roadmap_preserves_progress_for_openrouter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """When refreshing a roadmap after completing tasks, OpenRouter receives the real progress."""
    captured = _mock_openrouter(monkeypatch, json.dumps(_valid_openrouter_payload(completed_count=2)))

    assert client.post("/api/v1/profile", json=_sample_payload()).status_code == 200
    created = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert created.status_code == 200

    # Mark 2 tasks completed
    for item in created.json()["weekly_plan"][:2]:
        assert client.patch(f"/api/v1/tasks/{item['task_id']}", json={"completed": True}).status_code == 200

    # Refresh via POST /roadmaps/{ROLE_ID}
    refreshed = client.post(f"/api/v1/roadmaps/{ROLE_ID}")
    assert refreshed.status_code == 200
    context = json.loads(captured["request"]["messages"][1]["content"])
    assert context["progress"]["completed_task_count"] == 2
    assert len(context["progress"]["completed_milestone_ids"]) == 2
    assert refreshed.json()["adaptation_note"]


def test_prompt_payload_carries_computed_timeline_facts_and_honesty_rules(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """Feasibility is computed in code and sent as facts the model must not derive."""
    captured = _mock_openrouter(monkeypatch, json.dumps(_valid_openrouter_payload()))

    personalization.personalize_roadmap_response(
        _roadmap(), _recommendation(), _constraints(), configured_openrouter
    )

    context = json.loads(captured["request"]["messages"][1]["content"])
    learner = context["learner"]
    assert learner["total_milestone_hours"] == 58  # 8+12+14+8+16 from the catalog
    assert learner["weeks_needed"] == 3.9  # 58 / 15, not model-derived
    assert learner["target_timeline_weeks"] == 12
    assert learner["timeline_feasible"] is True

    system_prompt = captured["request"]["messages"][0]["content"]
    assert "never recalculate them" in system_prompt
    assert "longer than" in system_prompt and "rather than asserting the plan fits" in system_prompt
    assert "literally present in learner.strongest_skills" in system_prompt
    assert "lower-alignment path" in system_prompt


def test_infeasible_timeline_without_stated_concern_falls_back(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """3 hrs/week against 58 milestone hours needs 19.3 weeks > 12-week target."""
    dishonest = _payload_with_texts(
        "The 12-week target works well for this plan and the steady milestone order keeps momentum. "
        "Each week builds directly toward the final portfolio deliverable.",
        "Work through this milestone steadily inside your weekly plan.",
    )
    _mock_openrouter(monkeypatch, json.dumps(dishonest))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _recommendation(), _weak_constraints(), configured_openrouter
    )

    assert result.generation_mode == "fallback"
    # The deterministic fallback must state the real mismatch itself.
    assert "longer than" in result.fit_explanation
    assert "19.3" in result.fit_explanation
    assert all(item.personalized_focus for item in result.weekly_plan)


def test_infeasible_timeline_with_honest_concern_is_kept(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    honest = _payload_with_texts(
        "At your current pace this will take approximately 19.3 weeks, longer than the 12-week target. "
        "The milestones still order the missing skills sensibly.",
        "Budget about 3 hours per week here and expect the timeline to stay stretched.",
    )
    _mock_openrouter(monkeypatch, json.dumps(honest))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _recommendation(), _weak_constraints(), configured_openrouter
    )

    assert result.generation_mode == "llm"
    assert "longer than" in result.fit_explanation


def test_empty_strongest_skills_with_fabricated_traits_falls_back(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    fabricated = _payload_with_texts(
        "This is a lower-alignment path at 36 fit given the supplied interests. "
        "The milestones still build the missing core skills in order.",
        "Your analytical mindset and attention to detail will help you absorb these concepts quickly.",
    )
    _mock_openrouter(monkeypatch, json.dumps(fabricated))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _weak_recommendation(), _constraints(), configured_openrouter
    )

    assert result.generation_mode == "fallback"
    # Honest deterministic text: low fit acknowledged, no invented strengths.
    assert "lower-alignment" in result.fit_explanation
    assert "analytical" not in " ".join(item.personalized_focus for item in result.weekly_plan)


def test_empty_strongest_skills_with_clean_output_is_kept(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    clean = _payload_with_texts(
        "This is a lower-alignment path at 36 fit given the supplied interests. "
        "The milestones still close the listed core skill gaps step by step.",
        "Your profile shows no confirmed skills yet, so plan steady practice hours each week for it.",
    )
    _mock_openrouter(monkeypatch, json.dumps(clean))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _weak_recommendation(), _constraints(), configured_openrouter
    )

    assert result.generation_mode == "llm"


def test_partial_strongest_skills_with_unconfirmed_skill_falls_back(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """A real confirmed skill does not authorize fabricated React experience."""
    fabricated = _payload_with_texts(
        "This role reflects the supplied score and the listed gaps still need focused practice. "
        "Use the fixed milestones to build evidence for the missing skills.",
        "Your strong React skills should make this milestone feel familiar as you work through it.",
    )
    _mock_openrouter(monkeypatch, json.dumps(fabricated))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _python_only_recommendation(), _constraints(), configured_openrouter
    )

    assert result.generation_mode == "fallback"
    assert "React skills" not in " ".join(item.personalized_focus for item in result.weekly_plan)


def test_partial_strongest_skills_with_confirmed_skill_is_kept(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """The partial-list guard remains specific: it permits an actual Python attribution."""
    grounded = _payload_with_texts(
        "This role reflects the supplied score and the listed gaps still need focused practice. "
        "Use the fixed milestones to build evidence for the missing skills.",
        "Your Python skills can support deliberate practice while you close the listed gaps.",
    )
    _mock_openrouter(monkeypatch, json.dumps(grounded))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _python_only_recommendation(), _constraints(), configured_openrouter
    )

    assert result.generation_mode == "llm"


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="requires OPENROUTER_API_KEY to exercise the live OpenRouter pipeline",
)
def test_live_partial_skill_personalization_falls_back_if_model_fabricates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the real pipeline for a Python-only learner without making it flaky.

    The provider may return grounded prose on any given run. If its generated
    prose does contain an unsupported attribution, record the guard decision
    and require the pipeline to return the deterministic fallback.
    """
    settings = Settings(openrouter_api_key=os.environ["OPENROUTER_API_KEY"])
    guard_decisions: list[bool] = []
    original_guard = personalization._attributes_unsupplied_skills

    def recording_guard(text: str, confirmed_skills: list[str]) -> bool:
        decision = original_guard(text, confirmed_skills)
        guard_decisions.append(decision)
        return decision

    monkeypatch.setattr(personalization, "_attributes_unsupplied_skills", recording_guard)
    result = personalization.personalize_roadmap_response(
        _roadmap(), _python_only_recommendation(), _constraints(), settings
    )

    assert result.generation_mode in {"llm", "fallback"}
    if guard_decisions and guard_decisions[-1]:
        assert result.generation_mode == "fallback"


def test_weak_profile_combined_failure_falls_back_to_honest_deterministic_text(
    monkeypatch: pytest.MonkeyPatch, configured_openrouter: Settings
) -> None:
    """fit 36, no skills, 3 hrs/week: fabricated skills AND a false fit claim."""
    combined = _payload_with_texts(
        "This moderate match fits your 12-week plan comfortably with your structured approach. "
        "The milestones build on what you already know.",
        "Leveraging your solid programming background, this milestone should feel familiar.",
    )
    _mock_openrouter(monkeypatch, json.dumps(combined))

    result = personalization.personalize_roadmap_response(
        _roadmap(), _weak_recommendation(), _weak_constraints(), configured_openrouter
    )

    assert result.generation_mode == "fallback"
    assert "36/100" in result.fit_explanation
    assert "lower-alignment" in result.fit_explanation
    assert "longer than" in result.fit_explanation
