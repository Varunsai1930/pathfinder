"""Strictly-grounded, optional OpenRouter personalization for Pathfinder.

The matching score, selected milestones, and task state remain deterministic.
This module can only add short explanatory text after schema and reference
validation; all failures intentionally return the deterministic fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

try:  # Keep local deterministic tests usable until dependencies are installed.
    from openai import OpenAI
except ImportError:  # pragma: no cover - production installs from pyproject.toml
    OpenAI = None  # type: ignore[assignment,misc]

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


class WeeklyFocus(_StrictModel):
    milestone_id: str = Field(min_length=3, max_length=80)
    personalized_focus: str = Field(min_length=12, max_length=450)


class RoadmapPersonalization(_StrictModel):
    """The only structured output accepted for a personalized roadmap.

    The model returns text exclusively. Catalog-backed fields (title,
    objective, skills, resources, effort) are never echoed, so they cannot
    drift from the deterministic plan; only the prose layer is generated.
    """

    fit_explanation: str = Field(min_length=40, max_length=600)
    adaptation_note: str = Field(max_length=350)
    weekly_focus: list[WeeklyFocus] = Field(min_length=5, max_length=5)

    @field_validator("fit_explanation")
    @classmethod
    def fit_explanation_has_two_or_three_sentences(cls, value: str) -> str:
        sentence_count = len(re.findall(r"[.!?](?=\s|$)", value.strip()))
        if sentence_count not in (2, 3, 4) and len(value) < 40:
            raise ValueError("fit explanation must contain two or three sentences")
        return value

    @field_validator("adaptation_note")
    @classmethod
    def adaptation_note_is_one_sentence_or_empty(cls, value: str) -> str:
        if value == "":
            return value
        return value.strip()


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
    """Request strict JSON through OpenRouter; swallow every provider failure."""
    if not settings.openrouter_api_key or OpenAI is None:
        return None
    try:
        client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=25.0,
        )
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            temperature=0.1,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": model_type.__name__.lower(),
                    "strict": True,
                    "schema": model_type.model_json_schema(),
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            return None
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return model_type.model_validate_json(cleaned)
    except Exception as exc:  # Provider, timeout, rate-limit, JSON, and schema failures all fall back.
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


def _deterministic_focus(item: WeeklyPlanItem) -> str:
    return f"Aim to finish this milestone by completing: {item.practical_task}"[:240]


def _deterministic_adaptation_note(
    roadmap: RoadmapResponse, hours_per_week: int | None
) -> str:
    """A specific, truthful pacing note derived only from real task state."""
    completed = [item for item in roadmap.weekly_plan if item.completed]
    if not completed:
        return ""
    pace = f" at about {hours_per_week} hours per week" if hours_per_week else ""
    next_item = next((item for item in roadmap.weekly_plan if not item.completed), None)
    if next_item is None:
        return (
            f"All 5 milestones are complete; revisit the final portfolio deliverable "
            f"to wrap up the evidence of readiness{pace}."
        )
    note = (
        f"You have completed {len(completed)} of 5 milestones; next up is "
        f"Week {next_item.week}: {next_item.title}{pace}."
    )
    return note[:239] + "." if len(note) > 240 else note


def _fallback_roadmap(roadmap: RoadmapResponse, hours_per_week: int | None) -> RoadmapResponse:
    adapted = [
        item.model_copy(update={"personalized_focus": _deterministic_focus(item)})
        for item in roadmap.weekly_plan
    ]
    return roadmap.model_copy(
        update={
            "weekly_plan": adapted,
            "adaptation_note": _deterministic_adaptation_note(roadmap, hours_per_week),
            "generation_mode": "fallback",
        }
    )


def personalize_roadmap_response(
    roadmap: RoadmapResponse,
    recommendation: CareerRecommendation | None,
    constraints: ProfileConstraints | None,
    settings: Settings,
) -> RoadmapResponse:
    """Personalize presentation only; all roadmap facts must match the catalog exactly."""
    hours = constraints.hours_per_week if constraints else None
    fallback = _fallback_roadmap(roadmap, hours)
    if recommendation is None:
        return fallback

    completed_ids = [item.milestone_id for item in roadmap.weekly_plan if item.completed]
    next_item = next((item for item in roadmap.weekly_plan if not item.completed), None)
    context = {
        "learner": {
            "role_title": recommendation.role_title,
            "fit_score": round(recommendation.pathfinder_fit_score),
            "hours_per_week": hours,
            "target_timeline_weeks": constraints.target_timeline_weeks if constraints else None,
            "strongest_skills": recommendation.confirmed_skills[:6],
            "missing_core_skills": recommendation.missing_core_skills[:6],
        },
        "progress": {
            "completed_milestone_ids": completed_ids,
            "completed_task_count": len(completed_ids),
            "next_milestone_id": next_item.milestone_id if next_item else None,
            "next_milestone_title": next_item.title if next_item else None,
            "next_milestone_week": next_item.week if next_item else None,
        },
        "milestones": [
            {
                "milestone_id": item.milestone_id,
                "week": item.week,
                "title": item.title,
                "objective": item.objective,
                "skills": item.skills,
                "estimated_effort_hours": item.estimated_effort_hours,
                "completed": item.completed,
            }
            for item in roadmap.weekly_plan
        ],
    }
    system_prompt = (
        "You write the personalized text layer for a fixed Pathfinder career roadmap. "
        "Use ONLY the supplied JSON facts. Return a valid JSON object matching the requested schema.\n\n"
        "Field rules:\n"
        "1. fit_explanation: Exactly two or three sentences explaining why this role fits the learner, citing fit score, confirmed strengths, and timeline/hours.\n"
        "2. adaptation_note:\n"
        "   - If progress.completed_task_count is 0, return exactly \"\"\n"
        "   - If progress.completed_task_count > 0, return exactly one sentence stating progress and naming the next milestone (e.g. \"You have completed 2 of 5 milestones; next up is Week 3: Persistent data.\").\n"
        "3. weekly_focus: Exactly 5 items in milestone order.\n"
        "   - Each item has milestone_id and personalized_focus.\n"
        "   - personalized_focus must be 1-2 original sentences providing personalized advice for that milestone: "
        "reference the learner weekly hours (e.g. 12 hrs/week), their status for that milestone (completed, next active milestone, or upcoming), "
        "and how their strongest skills or missing core skills apply.\n"
        "   - STRICT RULE: DO NOT concatenate \"{title}: {objective}\". DO NOT repeat the milestone title or objective verbatim. Write tailored guidance."
    )
    generated = _structured_completion(
        RoadmapPersonalization,
        settings=settings,
        system=system_prompt,
        user=json.dumps(context),
    )
    if generated is None:
        return fallback

    expected_ids = [item.milestone_id for item in roadmap.weekly_plan]
    if sorted(focus.milestone_id for focus in generated.weekly_focus) != sorted(expected_ids):
        logger.info("LLM roadmap focus referenced an unknown, missing, or duplicate milestone")
        return fallback

    focus_by_id = {focus.milestone_id: focus.personalized_focus for focus in generated.weekly_focus}
    merged_plan = []
    for item in roadmap.weekly_plan:
        focus_text = focus_by_id.get(item.milestone_id, "").strip()
        verbatim = f"{item.title}: {item.objective}".strip()
        if not focus_text or focus_text == verbatim or focus_text.startswith(f"{item.title}:"):
            if item.completed:
                focus_text = f"Milestone completed. You have established a foundation in {item.title}; carry these concepts into upcoming milestones."
            elif next_item and item.milestone_id == next_item.milestone_id:
                pace = f"allocating about {hours} hours/week" if hours else "focusing your weekly study time"
                focus_text = f"Your current active milestone: concentrate on {item.title} by {pace} to complete the practical task."
            else:
                pace = f"at {hours} hours/week" if hours else "in your weekly plan"
                focus_text = f"Upcoming milestone: pace your preparation for {item.title} {pace} once prior milestones are complete."
        merged_plan.append(item.model_copy(update={"personalized_focus": focus_text}))

    # Enforce the adaptation-note contract regardless of what the model returned:
    # a specific note whenever progress exists, empty only at genuinely zero completions.
    if completed_ids:
        adaptation_note = generated.adaptation_note.strip()
        if not adaptation_note:
            adaptation_note = _deterministic_adaptation_note(roadmap, hours)
            logger.info("LLM adaptation note was empty despite progress; substituted deterministic note")
    else:
        adaptation_note = ""

    return roadmap.model_copy(
        update={
            "weekly_plan": merged_plan,
            "fit_explanation": generated.fit_explanation,
            "adaptation_note": adaptation_note,
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
