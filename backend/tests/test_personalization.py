"""Tests for strict, failure-safe LLM personalization and bounded Q&A."""

from fastapi.testclient import TestClient

from app import personalization
from app.personalization import FitExplanationBatch, GroundedAnswer, RoadmapPersonalization


def _sample_payload() -> dict:
    return {
        "interest_responses": {
            "realistic-1": 5, "realistic-2": 4, "realistic-3": 3,
            "investigative-1": 2, "investigative-2": 1, "investigative-3": 5,
            "artistic-1": 4, "artistic-2": 3, "artistic-3": 2,
            "social-1": 1, "social-2": 5, "social-3": 4,
            "enterprising-1": 3, "enterprising-2": 2, "enterprising-3": 1,
            "conventional-1": 5, "conventional-2": 4, "conventional-3": 3,
        },
        "skill_confidence": {"python": "practised", "javascript": "project-ready", "sql": "aware", "git": "project-ready"},
        "work_style_responses": {"analytical": 5, "creative": 3, "collaborative": 4, "structured": 4, "systems_oriented": 5},
        "constraints": {"hours_per_week": 15, "target_timeline_weeks": 12, "career_certainty": "deciding"},
    }


def test_no_key_uses_fallback_personalization(client: TestClient) -> None:
    client.post("/api/v1/profile", json=_sample_payload())
    match = client.post("/api/v1/match")
    assert match.status_code == 200
    assert match.json()["generation_mode"] == "fallback"
    assert all(rec["fit_explanation"] for rec in match.json()["recommendations"])

    roadmap = client.post("/api/v1/roadmaps/frontend-developer")
    assert roadmap.status_code == 200
    assert roadmap.json()["generation_mode"] == "fallback"
    assert roadmap.json()["adaptation_note"]
    assert all(item["personalized_focus"] for item in roadmap.json()["weekly_plan"])


def test_valid_mocked_llm_results_are_accepted(client: TestClient, monkeypatch) -> None:
    def fake_completion(model_type, **_kwargs):
        if model_type is FitExplanationBatch:
            return FitExplanationBatch.model_validate({"explanations": [
                {"role_id": "frontend-developer", "fit_explanation": "This result uses your displayed score data. Follow the listed skill gaps next."},
                {"role_id": "backend-developer", "fit_explanation": "This result uses your displayed score data. Follow the listed skill gaps next."},
                {"role_id": "cloud-devops-engineer", "fit_explanation": "This result uses your displayed score data. Follow the listed skill gaps next."},
                {"role_id": "data-analyst", "fit_explanation": "This result uses your displayed score data. Follow the listed skill gaps next."},
            ]})
        if model_type is RoadmapPersonalization:
            return RoadmapPersonalization.model_validate({
                "milestone_focuses": [
                    {"milestone_id": milestone_id, "personalized_focus": "Complete the supplied task and use the listed skill for this milestone."}
                    for milestone_id in ["frontend-web-foundations", "frontend-javascript", "frontend-react", "frontend-quality", "frontend-portfolio"]
                ],
                "adaptation_note": "Use the supplied weekly hours to complete the fixed milestones in their given order.",
            })
        if model_type is GroundedAnswer:
            return GroundedAnswer(answer="Your result card shows the relevant fit data and skill gaps.", referenced_role_ids=["frontend-developer"], referenced_milestone_ids=[])
        return None

    monkeypatch.setattr(personalization, "_structured_completion", fake_completion)
    client.post("/api/v1/profile", json=_sample_payload())
    match = client.post("/api/v1/match")
    assert match.json()["generation_mode"] == "llm"

    roadmap = client.post("/api/v1/roadmaps/frontend-developer")
    assert roadmap.json()["generation_mode"] == "llm"
    assert roadmap.json()["weekly_plan"][0]["personalized_focus"]

    response = client.post("/api/v1/questions", json={"question": "What should I improve?"})
    assert response.status_code == 200
    assert response.json()["generation_mode"] == "llm"


def test_unowned_llm_question_reference_falls_back(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        personalization,
        "_structured_completion",
        lambda model_type, **_kwargs: GroundedAnswer(
            answer="This should not be used because it cites an unknown role.",
            referenced_role_ids=["not-a-real-role"],
            referenced_milestone_ids=[],
        ) if model_type is GroundedAnswer else None,
    )
    client.post("/api/v1/profile", json=_sample_payload())
    response = client.post("/api/v1/questions", json={"question": "Which gap should I learn first?"})
    assert response.status_code == 200
    assert response.json()["generation_mode"] == "fallback"
