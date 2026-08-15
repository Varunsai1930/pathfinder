"""Grounded, fully deterministic matching and gap-scoring functions."""

from __future__ import annotations

import math
from collections import defaultdict

from fastapi import HTTPException, status

from app.catalog.assessment_loader import get_assessment_catalog
from app.catalog.loader import get_catalog
from app.catalog.models import RiasecDimension, RiasecProfile, RoleDefinition, SkillTier, WorkStyleProfile
from app.matching.models import (
    CareerRecommendation,
    MatchProfile,
    MatchResponse,
    ScoreBreakdown,
    SkillConfidence,
)


CONFIDENCE_WEIGHTS = {
    SkillConfidence.NONE: 0.0,
    SkillConfidence.AWARE: 0.3,
    SkillConfidence.PRACTISED: 0.7,
    SkillConfidence.PROJECT_READY: 1.0,
}
CONFIRMED_CONFIDENCE_LEVELS = {
    SkillConfidence.PRACTISED,
    SkillConfidence.PROJECT_READY,
}
TIER_WEIGHTS = {
    SkillTier.CORE: 1.0,
    SkillTier.SUPPORTING: 0.5,
    SkillTier.OPTIONAL: 0.25,
}
RIASEC_FIELDS = tuple(dimension.value for dimension in RiasecDimension)
WORK_STYLE_FIELDS = (
    "analytical",
    "creative",
    "collaborative",
    "structured",
    "systems_oriented",
)


def _scale_response(value: int) -> float:
    """Map a one-to-five response to the catalog's zero-to-one-hundred target scale."""
    return (value - 1) * 25.0


def _profile_similarity(user_values: list[float], target_values: list[float]) -> float:
    """Return 0–100 similarity using cosine similarity (magnitude-invariant)."""
    dot = sum(u * t for u, t in zip(user_values, target_values))
    mag_u = math.sqrt(sum(u * u for u in user_values))
    mag_t = math.sqrt(sum(t * t for t in target_values))
    if mag_u == 0.0 or mag_t == 0.0:
        return 0.0
    return round(max(0.0, 100 * dot / (mag_u * mag_t)), 2)


def _normalize_interest_profile(profile: MatchProfile) -> RiasecProfile:
    assessment = get_assessment_catalog()
    expected_ids = {question.id for question in assessment.interest_questions}
    supplied_ids = set(profile.interest_responses)
    if supplied_ids != expected_ids:
        missing = sorted(expected_ids - supplied_ids)
        unknown = sorted(supplied_ids - expected_ids)
        detail = {"message": "Interest responses must include every assessment question exactly once.", "missing": missing, "unknown": unknown}
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

    totals: dict[RiasecDimension, list[int]] = defaultdict(list)
    for question in assessment.interest_questions:
        answer = profile.interest_responses[question.id]
        if not 1 <= answer <= 5:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{question.id} must be an integer from 1 to 5.")
        totals[question.dimension].append(answer)

    return RiasecProfile(
        **{
            dimension.value: round(sum(totals[dimension]) / len(totals[dimension]) * 25 - 25)
            for dimension in RiasecDimension
        }
    )


def _normalize_work_style_profile(profile: MatchProfile) -> WorkStyleProfile:
    return WorkStyleProfile(
        **{
            field: round(_scale_response(getattr(profile.work_style_responses, field)))
            for field in WORK_STYLE_FIELDS
        }
    )


def _validate_skill_ids(profile: MatchProfile) -> None:
    known_skill_ids = {skill.id for skill in get_assessment_catalog().skills}
    unknown = sorted(set(profile.skill_confidence) - known_skill_ids)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Unknown skill IDs are not accepted.", "unknown": unknown},
        )


def _score_role(
    role: RoleDefinition,
    interest_profile: RiasecProfile,
    work_style_profile: WorkStyleProfile,
    skill_confidence: dict[str, SkillConfidence],
) -> CareerRecommendation:
    interest_score = _profile_similarity(
        [getattr(interest_profile, field) for field in RIASEC_FIELDS],
        [getattr(role.riasec, field) for field in RIASEC_FIELDS],
    )
    work_style_score = _profile_similarity(
        [getattr(work_style_profile, field) for field in WORK_STYLE_FIELDS],
        [getattr(role.work_style, field) for field in WORK_STYLE_FIELDS],
    )
    total_tier_weight = sum(TIER_WEIGHTS[skill.tier] for skill in role.skills)
    readiness_weight = sum(
        TIER_WEIGHTS[skill.tier] * CONFIDENCE_WEIGHTS[skill_confidence.get(skill.id, SkillConfidence.NONE)]
        for skill in role.skills
    )
    skill_score = round(100 * readiness_weight / total_tier_weight, 2)
    confirmed_skills = [
        skill.name
        for skill in role.skills
        if skill_confidence.get(skill.id, SkillConfidence.NONE) in CONFIRMED_CONFIDENCE_LEVELS
    ]
    missing_core_skills = [
        skill.name
        for skill in role.skills
        if skill.tier == SkillTier.CORE
        and skill_confidence.get(skill.id, SkillConfidence.NONE) not in CONFIRMED_CONFIDENCE_LEVELS
    ]
    missing_supporting_skills = [
        skill.name
        for skill in role.skills
        if skill.tier == SkillTier.SUPPORTING
        and skill_confidence.get(skill.id, SkillConfidence.NONE) not in CONFIRMED_CONFIDENCE_LEVELS
    ]
    total_score = round(0.55 * interest_score + 0.35 * skill_score + 0.10 * work_style_score, 2)
    return CareerRecommendation(
        rank=1,
        role_id=role.id,
        role_title=role.title,
        pathfinder_fit_score=total_score,
        score_breakdown=ScoreBreakdown(
            interest_alignment=interest_score,
            skill_readiness=skill_score,
            work_style_alignment=work_style_score,
        ),
        confirmed_skills=confirmed_skills,
        missing_core_skills=missing_core_skills,
        missing_supporting_skills=missing_supporting_skills,
    )


def match_profile(profile: MatchProfile) -> MatchResponse:
    """Rank all supported paths from the same transparent weighted model."""
    _validate_skill_ids(profile)
    interest_profile = _normalize_interest_profile(profile)
    work_style_profile = _normalize_work_style_profile(profile)
    recommendations = [
        _score_role(role, interest_profile, work_style_profile, profile.skill_confidence)
        for role in get_catalog().roles
    ]
    recommendations.sort(key=lambda recommendation: (-recommendation.pathfinder_fit_score, recommendation.role_id))
    ranked = [recommendation.model_copy(update={"rank": index}) for index, recommendation in enumerate(recommendations, start=1)]
    return MatchResponse(
        normalized_interest_profile=interest_profile,
        normalized_work_style_profile=work_style_profile,
        recommendations=ranked,
    )
