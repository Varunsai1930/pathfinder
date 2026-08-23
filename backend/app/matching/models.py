from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import RiasecProfile, WorkStyleProfile


class SkillConfidence(str, Enum):
    NONE = "none"
    AWARE = "aware"
    PRACTISED = "practised"
    PROJECT_READY = "project-ready"


class WorkStyleResponses(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analytical: int = Field(ge=1, le=5)
    creative: int = Field(ge=1, le=5)
    collaborative: int = Field(ge=1, le=5)
    structured: int = Field(ge=1, le=5)
    systems_oriented: int = Field(ge=1, le=5)


class MatchProfile(BaseModel):
    """User-supplied evidence used by the deterministic matching engine."""

    model_config = ConfigDict(extra="forbid")

    interest_responses: dict[str, int] = Field(min_length=18, max_length=18)
    skill_confidence: dict[str, SkillConfidence] = Field(default_factory=dict)
    work_style_responses: WorkStyleResponses


class CareerCertainty(str, Enum):
    EXPLORING = "exploring"
    DECIDING = "deciding"
    COMMITTED = "committed"


class ProfileConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours_per_week: int = Field(ge=1, le=168)
    target_timeline_weeks: int = Field(ge=1, le=104)
    career_certainty: CareerCertainty


class ProfilePayload(BaseModel):
    """Full assessment payload submitted to POST /profile."""

    model_config = ConfigDict(extra="forbid")

    interest_responses: dict[str, int] = Field(min_length=18, max_length=18)
    skill_confidence: dict[str, SkillConfidence] = Field(default_factory=dict)
    work_style_responses: WorkStyleResponses
    constraints: ProfileConstraints
    # Free-text goal from the conversational intake; optional so manual
    # assessment submissions (and older clients) stay valid. Absent keeps the
    # previously stored goal; a non-empty value overwrites it.
    goal_text: str | None = Field(default=None, max_length=2000)


class ProfileResponse(BaseModel):
    """Persisted user profile returned from GET /profile."""

    model_config = ConfigDict(extra="forbid")

    interest_responses: dict[str, int]
    skill_confidence: dict[str, SkillConfidence]
    work_style_responses: WorkStyleResponses
    constraints: ProfileConstraints
    goal_text: str | None = None


class ScoreBreakdown(BaseModel):
    interest_alignment: float = Field(ge=0, le=100)
    skill_readiness: float = Field(ge=0, le=100)
    work_style_alignment: float = Field(ge=0, le=100)


class CareerRecommendation(BaseModel):
    rank: int = Field(ge=1)
    role_id: str
    role_title: str
    pathfinder_fit_score: float = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    confirmed_skills: list[str]
    missing_core_skills: list[str]
    missing_supporting_skills: list[str]
    fit_explanation: str = ""


class MatchResponse(BaseModel):
    normalized_interest_profile: RiasecProfile
    normalized_work_style_profile: WorkStyleProfile
    recommendations: list[CareerRecommendation] = Field(min_length=4, max_length=12)
    generation_mode: str = "fallback"
