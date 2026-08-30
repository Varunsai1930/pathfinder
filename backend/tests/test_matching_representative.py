"""Representative profile tests and score-breakdown integrity.

One representative profile per intended top role, plus a score-sum
assertion confirming the 55/35/10 breakdown reconstructs the total.
"""

import pytest

from app.catalog.assessment_loader import get_assessment_catalog
from app.matching.models import MatchProfile, SkillConfidence, WorkStyleResponses
from app.matching.service import match_profile


def _build_profile(
    *,
    interest_emphasis: dict[str, int],
    skills: dict[str, SkillConfidence],
    work_style: WorkStyleResponses,
) -> MatchProfile:
    """Build a MatchProfile with dimension-specific interest emphasis.

    ``interest_emphasis`` maps a RIASEC dimension name to a 1–5 score.
    Dimensions not listed default to 2 (slightly-like-me baseline).
    """
    assessment = get_assessment_catalog()
    responses: dict[str, int] = {}
    for q in assessment.interest_questions:
        responses[q.id] = interest_emphasis.get(q.dimension.value, 2)
    return MatchProfile(
        interest_responses=responses,
        skill_confidence=skills,
        work_style_responses=work_style,
    )


# ---------------------------------------------------------------------------
# Representative profiles — one per intended top role
# ---------------------------------------------------------------------------

FRONTEND_PROFILE = _build_profile(
    interest_emphasis={

        "artistic": 5, "investigative": 4, "social": 4, "conventional": 2, "realistic": 2, "enterprising": 2

    },
    skills={
        "html-css": SkillConfidence.PRACTISED,
        "javascript": SkillConfidence.PRACTISED,
        "react": SkillConfidence.AWARE,
        "git": SkillConfidence.PRACTISED,
        "accessibility": SkillConfidence.AWARE,
    },
    work_style=WorkStyleResponses(analytical=3, creative=5, collaborative=4, structured=3, systems_oriented=3),
)

BACKEND_PROFILE = _build_profile(
    interest_emphasis={
        "investigative": 5, "conventional": 5, "realistic": 3, "artistic": 1, "social": 2, "enterprising": 2
    },
    skills={
        "python": SkillConfidence.PRACTISED,
        "api-design": SkillConfidence.AWARE,
        "sql": SkillConfidence.PRACTISED,
        "git": SkillConfidence.PRACTISED,
        "authentication": SkillConfidence.AWARE,
    },
    work_style=WorkStyleResponses(analytical=5, creative=2, collaborative=3, structured=5, systems_oriented=5),
)

DATA_ANALYST_PROFILE = _build_profile(
    interest_emphasis={
        "investigative": 5, "conventional": 5, "social": 3, "realistic": 3, "artistic": 3, "enterprising": 3
    },
    skills={
        "sql": SkillConfidence.PRACTISED,
        "spreadsheets": SkillConfidence.PROJECT_READY,
        "python": SkillConfidence.AWARE,
        "data-visualization": SkillConfidence.PRACTISED,
        "statistics": SkillConfidence.AWARE,
    },
    work_style=WorkStyleResponses(analytical=5, creative=3, collaborative=3, structured=5, systems_oriented=3),
)

CLOUD_DEVOPS_PROFILE = _build_profile(
    interest_emphasis={
        "realistic": 5, "investigative": 5, "conventional": 5, "artistic": 1, "social": 2, "enterprising": 2
    },
    skills={
        "linux": SkillConfidence.PRACTISED,
        "git": SkillConfidence.PROJECT_READY,
        "cloud-basics": SkillConfidence.AWARE,
        "containers": SkillConfidence.AWARE,
        "ci-cd": SkillConfidence.AWARE,
    },
    work_style=WorkStyleResponses(analytical=5, creative=2, collaborative=3, structured=5, systems_oriented=5),
)


DATA_ENGINEER_PROFILE = _build_profile(
    interest_emphasis={
        "conventional": 5, "investigative": 4, "realistic": 4, "artistic": 1, "social": 2, "enterprising": 2
    },
    skills={
        "sql": SkillConfidence.PRACTISED,
        "python": SkillConfidence.PRACTISED,
        "linux": SkillConfidence.AWARE,
        "containers": SkillConfidence.AWARE,
        "git": SkillConfidence.PRACTISED,
    },
    work_style=WorkStyleResponses(analytical=5, creative=2, collaborative=3, structured=5, systems_oriented=5),
)

SECURITY_PROFILE = _build_profile(
    interest_emphasis={
        "investigative": 5, "realistic": 4, "conventional": 4, "artistic": 1, "social": 2, "enterprising": 2
    },
    skills={
        "linux": SkillConfidence.PRACTISED,
        "python": SkillConfidence.PRACTISED,
        "authentication": SkillConfidence.AWARE,
        "monitoring": SkillConfidence.AWARE,
        "containers": SkillConfidence.AWARE,
    },
    work_style=WorkStyleResponses(analytical=5, creative=3, collaborative=3, structured=4, systems_oriented=5),
)


@pytest.mark.parametrize(
    "profile, expected_top_role",
    [
        (FRONTEND_PROFILE, "frontend-developer"),
        (BACKEND_PROFILE, "backend-developer"),
        (DATA_ANALYST_PROFILE, "data-analyst"),
        (CLOUD_DEVOPS_PROFILE, "cloud-devops-engineer"),
        (SECURITY_PROFILE, "security-analyst"),
        (DATA_ENGINEER_PROFILE, "data-engineer"),
    ],
    ids=["frontend", "backend", "data-analyst", "cloud-devops", "security", "data-engineer"],
)
def test_representative_profile_ranks_intended_role_first(
    profile: MatchProfile, expected_top_role: str
) -> None:
    """Each representative profile must rank its intended role first."""
    result = match_profile(profile)
    top = result.recommendations[0]
    assert top.role_id == expected_top_role, (
        f"Expected {expected_top_role} at rank 1, got {top.role_id} "
        f"(score {top.pathfinder_fit_score}). "
        f"Full ranking: {[(r.role_id, r.pathfinder_fit_score) for r in result.recommendations]}"
    )


# ---------------------------------------------------------------------------
# Score breakdown integrity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "profile",
    [
        FRONTEND_PROFILE,
        BACKEND_PROFILE,
        DATA_ANALYST_PROFILE,
        CLOUD_DEVOPS_PROFILE,
        SECURITY_PROFILE,
        DATA_ENGINEER_PROFILE,
    ],
    ids=["frontend", "backend", "data-analyst", "cloud-devops", "security", "data-engineer"],
)
def test_score_breakdown_reconstructs_total(profile: MatchProfile) -> None:
    """0.55 * interest + 0.35 * skill + 0.10 * work_style must equal the total fit score."""
    result = match_profile(profile)
    for rec in result.recommendations:
        b = rec.score_breakdown
        reconstructed = round(0.55 * b.interest_alignment + 0.35 * b.skill_readiness + 0.10 * b.work_style_alignment, 2)
        assert rec.pathfinder_fit_score == reconstructed, (
            f"{rec.role_id}: total {rec.pathfinder_fit_score} != "
            f"0.55*{b.interest_alignment} + 0.35*{b.skill_readiness} + 0.10*{b.work_style_alignment} "
            f"= {reconstructed}"
        )


@pytest.mark.parametrize(
    "profile",
    [
        FRONTEND_PROFILE,
        BACKEND_PROFILE,
        DATA_ANALYST_PROFILE,
        CLOUD_DEVOPS_PROFILE,
        SECURITY_PROFILE,
        DATA_ENGINEER_PROFILE,
    ],
    ids=["frontend", "backend", "data-analyst", "cloud-devops", "security", "data-engineer"],
)
def test_confirmed_and_missing_skills_have_zero_overlap(profile: MatchProfile) -> None:
    """A skill cannot be both confirmed and missing for the same role."""
    result = match_profile(profile)
    for rec in result.recommendations:
        confirmed = set(rec.confirmed_skills)
        missing_core = set(rec.missing_core_skills)
        missing_supporting = set(rec.missing_supporting_skills)
        missing_all = missing_core | missing_supporting

        overlap = confirmed & missing_all
        assert not overlap, (
            f"Role '{rec.role_id}' has overlapping confirmed and missing skills: {overlap}"
        )

