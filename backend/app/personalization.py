"""Strictly-grounded, optional OpenAI personalization for Pathfinder.

The matching score, selected milestones, and task state remain deterministic.
This module can only add short explanatory text after schema and reference
validation; all failures intentionally return the deterministic fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.config import Settings
from app.matching.models import CareerRecommendation, MatchResponse, ProfileConstraints
from app.roadmap_models import RoadmapResponse, WeeklyPlanItem

logger = logging.getLogger(__name__)
_OutputModel = TypeVar("_OutputModel", bound=BaseModel)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FitExplanation(_StrictModel):
    role_id: str = Field(min_length=3, max_length=80)
    fit_explanation: str = Field(min_length=40, max_length=420)

    @field_validator("fit_explanation")
    @classmethod
    def must_have_two_or_three_sentences(cls, value: str) -> str:
        sentence_count = len(re.findall(r"[.!?](?=\s|$)", value.strip()))
        if sentence_count not in (2, 3):
            raise ValueError("fit explanation must contain two or three sentences")
        return value


class FitExplanationBatch(_StrictModel):
    explanations: list[FitExplanation] = Field(min_length=4, max_length=4)


class MilestoneFocus(_StrictModel):
    milestone_id: str = Field(min_length=3, max_length=100)
    personalized_focus: str = Field(min_length=12, max_length=240)


class RoadmapPersonalization(_StrictModel):
    milestone_focuses: list[MilestoneFocus] = Field(min_length=5, max_length=5)
    adaptation_note: str = Field(min_length=20, max_length=240)


class AskQuestionPayload(_StrictModel):
    question: str = Field(min_length=3, max_length=500)
    role_id: str | None = Field(default=None, min_length=3, max_length=80)


class GroundedAnswer(_StrictModel):
    answer: str = Field(min_length=20, max_length=600)
    referenced_role_ids: list[str] = Field(default_factory=list, max_length=4)
    referenced_milestone_ids: list[str] = Field(default_factory=list, max_length=5)


class AskQuestionResponse(_StrictModel):
    answer: str
    generation_mode: str


def _structured_completion(
    model_type: type[_OutputModel], *, system: str, user: str, settings: Settings
) -> _OutputModel | None:
    """Request strict JSON from OpenAI; swallow every provider/parse failure."""
    if not settings.openai_api_key:
        return None
    payload = {
        "model": settings.openai_model,
        "temperature": 0.2,
        "max_completion_tokens": 700,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": model_type.__name__.lower(),
                "strict": True,
                "schema": model_type.model_json_schema(),
            },
        },
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return model_type.model_validate_json(content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        logger.info("Grounded LLM generation fell back to deterministic content: %s", exc)
        return None


def _fallback_fit_explanation(recommendation: CareerRecommendation) -> str:
    breakdown = recommendation.score_breakdown
    strongest = max(
        (("interest alignment", breakdown.interest_alignment), ("skill readiness", breakdown.skill_readiness), ("work-style alignment", breakdown.work_style_alignment)),
        key=lambda item: item[1],
    )
    gaps = recommendation.missing_core_skills[:2]
    gap_sentence = (
        f"Focus next on {', '.join(gaps)} to strengthen your readiness."
        if gaps
        else "Your confirmed skills provide a solid base for the first milestone."
    )
    return (
        f"{recommendation.role_title} is ranked #{recommendation.rank} with a {round(recommendation.pathfinder_fit_score)} fit score, led by {strongest[0]}. "
        f"{gap_sentence}"
    )


def personalize_match_response(
    match: MatchResponse, constraints: ProfileConstraints, settings: Settings
) -> MatchResponse:
    """Add validated two-to-three sentence rationale per deterministic result."""
    fallback_recommendations = [
        recommendation.model_copy(update={"fit_explanation": _fallback_fit_explanation(recommendation)})
        for recommendation in match.recommendations
    ]
    context = {
        "hours_per_week": constraints.hours_per_week,
        "target_timeline_weeks": constraints.target_timeline_weeks,
        "career_certainty": constraints.career_certainty.value,
        "recommendations": [
            {
                "role_id": rec.role_id,
                "role_title": rec.role_title,
                "rank": rec.rank,
                "fit_score": rec.pathfinder_fit_score,
                "score_breakdown": rec.score_breakdown.model_dump(),
                "confirmed_skills": rec.confirmed_skills,
                "missing_core_skills": rec.missing_core_skills,
                "missing_supporting_skills": rec.missing_supporting_skills,
            }
            for rec in match.recommendations
        ],
    }
    generated = _structured_completion(
        FitExplanationBatch,
        settings=settings,
        system=(
            "You write short Pathfinder career-fit explanations. Use ONLY facts in the supplied JSON. "
            "Do not add careers, skills, scores, claims, resources, or advice not supplied. "
            "Return exactly one two-to-three sentence explanation for every supplied role."
        ),
        user=json.dumps(context),
    )
    if generated is None:
        return match.model_copy(update={"recommendations": fallback_recommendations, "generation_mode": "fallback"})

    allowed_ids = [rec.role_id for rec in match.recommendations]
    by_id = {item.role_id: item.fit_explanation for item in generated.explanations}
    if set(by_id) != set(allowed_ids) or len(by_id) != len(allowed_ids):
        logger.info("LLM fit explanations included an unknown, missing, or duplicate role")
        return match.model_copy(update={"recommendations": fallback_recommendations, "generation_mode": "fallback"})
    personalized = [rec.model_copy(update={"fit_explanation": by_id[rec.role_id]}) for rec in match.recommendations]
    return match.model_copy(update={"recommendations": personalized, "generation_mode": "llm"})


def _fallback_roadmap(roadmap: RoadmapResponse, hours_per_week: int | None) -> RoadmapResponse:
    focus = "Use the milestone objective and practical task as your focus this week."
    adapted = [item.model_copy(update={"personalized_focus": focus}) for item in roadmap.weekly_plan]
    pace = f"at about {hours_per_week} hours each week" if hours_per_week else "at a sustainable weekly pace"
    return roadmap.model_copy(
        update={
            "weekly_plan": adapted,
            "adaptation_note": f"Follow the five fixed milestones in order {pace}; task completion controls your next action.",
            "generation_mode": "fallback",
        }
    )


def personalize_roadmap_response(
    roadmap: RoadmapResponse, constraints: ProfileConstraints | None, settings: Settings
) -> RoadmapResponse:
    """Add focus notes without changing roadmap data, IDs, weeks, or tasks."""
    fallback = _fallback_roadmap(roadmap, constraints.hours_per_week if constraints else None)
    context = {
        "role_id": roadmap.role_id,
        "hours_per_week": constraints.hours_per_week if constraints else None,
        "target_timeline_weeks": constraints.target_timeline_weeks if constraints else None,
        "milestones": [
            {
                "milestone_id": item.milestone_id,
                "week": item.week,
                "title": item.title,
                "objective": item.objective,
                "skills": item.skills,
                "estimated_effort_hours": item.estimated_effort_hours,
                "practical_task": item.practical_task,
                "portfolio_deliverable": item.portfolio_deliverable,
            }
            for item in roadmap.weekly_plan
        ],
    }
    generated = _structured_completion(
        RoadmapPersonalization,
        settings=settings,
        system=(
            "You personalize a fixed Pathfinder roadmap. Use ONLY the JSON facts supplied. "
            "Return one brief focus for each existing milestone ID, in its supplied order, and one pacing note. "
            "Never invent or rename a milestone, skill, task, resource, estimate, or deadline."
        ),
        user=json.dumps(context),
    )
    if generated is None:
        return fallback
    expected_ids = [item.milestone_id for item in roadmap.weekly_plan]
    actual_ids = [item.milestone_id for item in generated.milestone_focuses]
    if actual_ids != expected_ids:
        logger.info("LLM roadmap personalization changed milestone IDs or order")
        return fallback
    focuses = {item.milestone_id: item.personalized_focus for item in generated.milestone_focuses}
    return roadmap.model_copy(
        update={
            "weekly_plan": [item.model_copy(update={"personalized_focus": focuses[item.milestone_id]}) for item in roadmap.weekly_plan],
            "adaptation_note": generated.adaptation_note,
            "generation_mode": "llm",
        }
    )


def fallback_question_answer(question: str, match: MatchResponse, roadmap: RoadmapResponse | None) -> str:
    """Useful bounded answer when LLM output is unavailable or ungrounded."""
    top = match.recommendations[0]
    query = question.lower()
    if roadmap and any(word in query for word in ("week", "plan", "roadmap", "milestone", "next", "task")):
        next_item = next((item for item in roadmap.weekly_plan if not item.completed), None)
        if next_item:
            return f"Your next roadmap step is Week {next_item.week}: {next_item.title}. Its practical task is: {next_item.practical_task}"
        return "All five milestones in this roadmap are complete. You can review the portfolio deliverable for the final evidence of readiness."
    if any(word in query for word in ("skill", "gap", "learn", "improve")):
        gaps = top.missing_core_skills or top.missing_supporting_skills
        if gaps:
            return f"For your top match, {top.role_title}, the first skill gaps shown are {', '.join(gaps[:3])}. Use the selected roadmap to work through them in milestone order."
    return f"Your top result is {top.role_title} (#{top.rank}, {round(top.pathfinder_fit_score)} fit score). Its strongest score component is shown on the result card; ask about a displayed role, skill gap, or roadmap milestone for a more specific answer."


def answer_grounded_question(
    payload: AskQuestionPayload,
    match: MatchResponse,
    roadmap: RoadmapResponse | None,
    settings: Settings,
) -> AskQuestionResponse:
    """Answer only from the caller's deterministic match and optional owned roadmap."""
    fallback = fallback_question_answer(payload.question, match, roadmap)
    context: dict[str, Any] = {
        "question": payload.question,
        "match": match.model_dump(mode="json", exclude={"normalized_interest_profile", "normalized_work_style_profile"}),
        "roadmap": roadmap.model_dump(mode="json") if roadmap else None,
    }
    generated = _structured_completion(
        GroundedAnswer,
        settings=settings,
        system=(
            "Answer a Pathfinder learner question using ONLY supplied match and roadmap facts. "
            "Do not use outside knowledge or infer facts. If the facts do not answer it, say that Pathfinder does not have that information. "
            "Keep the answer to one to three sentences and list every role or milestone ID you cite."
        ),
        user=json.dumps(context),
    )
    if generated is None:
        return AskQuestionResponse(answer=fallback, generation_mode="fallback")
    allowed_roles = {rec.role_id for rec in match.recommendations}
    allowed_milestones = {item.milestone_id for item in roadmap.weekly_plan} if roadmap else set()
    if not set(generated.referenced_role_ids).issubset(allowed_roles) or not set(generated.referenced_milestone_ids).issubset(allowed_milestones):
        logger.info("LLM Q&A answer included an unowned role or milestone")
        return AskQuestionResponse(answer=fallback, generation_mode="fallback")
    return AskQuestionResponse(answer=generated.answer, generation_mode="llm")
