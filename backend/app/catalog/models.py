from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class RiasecProfile(BaseModel):
    realistic: int = Field(ge=0, le=100)
    investigative: int = Field(ge=0, le=100)
    artistic: int = Field(ge=0, le=100)
    social: int = Field(ge=0, le=100)
    enterprising: int = Field(ge=0, le=100)
    conventional: int = Field(ge=0, le=100)


class WorkStyleProfile(BaseModel):
    analytical: int = Field(ge=0, le=100)
    creative: int = Field(ge=0, le=100)
    collaborative: int = Field(ge=0, le=100)
    structured: int = Field(ge=0, le=100)
    systems_oriented: int = Field(ge=0, le=100)


class SkillTier(str, Enum):
    CORE = "core"
    SUPPORTING = "supporting"
    OPTIONAL = "optional"


class SkillDomain(str, Enum):
    FOUNDATION = "foundation"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"


class SkillRequirement(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=80)
    tier: SkillTier


class SkillDefinition(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=80)
    domain: SkillDomain
    profile_prompt: str = Field(min_length=12, max_length=180)


class RiasecDimension(str, Enum):
    REALISTIC = "realistic"
    INVESTIGATIVE = "investigative"
    ARTISTIC = "artistic"
    SOCIAL = "social"
    ENTERPRISING = "enterprising"
    CONVENTIONAL = "conventional"


class InterestQuestion(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    dimension: RiasecDimension
    prompt: str = Field(min_length=15, max_length=220)


class AssessmentCatalog(BaseModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    purpose_note: str = Field(min_length=20, max_length=400)
    response_scale: list[str] = Field(min_length=5, max_length=5)
    interest_questions: list[InterestQuestion] = Field(min_length=18, max_length=18)
    skills: list[SkillDefinition] = Field(min_length=1, max_length=40)

    @field_validator("interest_questions")
    @classmethod
    def questions_are_unique_and_balanced(
        cls, questions: list[InterestQuestion]
    ) -> list[InterestQuestion]:
        if len({question.id for question in questions}) != len(questions):
            raise ValueError("interest question IDs must be unique")
        counts = {dimension: 0 for dimension in RiasecDimension}
        for question in questions:
            counts[question.dimension] += 1
        if any(count != 3 for count in counts.values()):
            raise ValueError("assessment needs exactly three questions per RIASEC dimension")
        return questions

    @field_validator("skills")
    @classmethod
    def skill_ids_are_unique(cls, skills: list[SkillDefinition]) -> list[SkillDefinition]:
        if len({skill.id for skill in skills}) != len(skills):
            raise ValueError("assessment skill IDs must be unique")
        return skills


class Resource(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    url: HttpUrl
    provider: str = Field(min_length=2, max_length=80)


class Milestone(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    sequence: int = Field(ge=1, le=5)
    title: str = Field(min_length=4, max_length=100)
    objective: str = Field(min_length=10, max_length=280)
    skills: list[str] = Field(min_length=1, max_length=6)
    estimated_effort_hours: int = Field(ge=3, le=40)
    practical_task: str = Field(min_length=10, max_length=280)
    portfolio_deliverable: str = Field(min_length=10, max_length=280)
    resources: list[Resource] = Field(min_length=1, max_length=3)


class PortfolioProject(BaseModel):
    title: str = Field(min_length=4, max_length=100)
    brief: str = Field(min_length=20, max_length=500)
    evidence_of_readiness: list[str] = Field(min_length=2, max_length=5)


class GroundingReference(BaseModel):
    """Explains how a Pathfinder path is grounded without claiming it is an O*NET occupation."""

    occupation_title: str = Field(min_length=4, max_length=120)
    relationship: str = Field(min_length=20, max_length=280)
    source_updated: str = Field(pattern=r"^\d{4}$")


class RoleDefinition(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=4, max_length=100)
    summary: str = Field(min_length=30, max_length=300)
    onet_soc_code: str = Field(pattern=r"^\d{2}-\d{4}\.\d{2}$")
    onet_reference_url: HttpUrl
    grounding: GroundingReference
    riasec: RiasecProfile
    work_style: WorkStyleProfile
    skills: list[SkillRequirement] = Field(min_length=4, max_length=20)
    milestones: list[Milestone] = Field(min_length=5, max_length=5)
    portfolio_project: PortfolioProject

    @field_validator("skills")
    @classmethod
    def skill_ids_are_unique(cls, skills: list[SkillRequirement]) -> list[SkillRequirement]:
        if len({skill.id for skill in skills}) != len(skills):
            raise ValueError("role skill IDs must be unique")
        return skills

    @model_validator(mode="after")
    def milestones_reference_known_skills(self) -> "RoleDefinition":
        known_skills = {skill.id for skill in self.skills}
        unknown = {skill_id for milestone in self.milestones for skill_id in milestone.skills} - known_skills
        if unknown:
            raise ValueError(f"milestones reference unknown skills: {sorted(unknown)}")
        if [milestone.sequence for milestone in self.milestones] != [1, 2, 3, 4, 5]:
            raise ValueError("role milestones must be sequenced from one through five")
        return self


class Catalog(BaseModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    roles: list[RoleDefinition] = Field(min_length=4, max_length=12)

    @field_validator("roles")
    @classmethod
    def role_ids_are_unique(cls, roles: list[RoleDefinition]) -> list[RoleDefinition]:
        if len({role.id for role in roles}) != len(roles):
            raise ValueError("role IDs must be unique")
        return roles


class CourseLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Course(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=4, max_length=120)
    provider: str = Field(min_length=2, max_length=80)
    url: HttpUrl
    skill_ids: list[str] = Field(min_length=1, max_length=3)
    prerequisites: list[str] = Field(default_factory=list, max_length=5)
    level: CourseLevel
    duration_hours: int = Field(ge=1, le=40)
    description: str = Field(min_length=20, max_length=280)

    @field_validator("skill_ids", "prerequisites")
    @classmethod
    def ids_are_valid_skill_pattern(cls, ids: list[str]) -> list[str]:
        for sid in ids:
            if not sid or not all(c.isalnum() or c == "-" for c in sid):
                raise ValueError(f"invalid skill id: {sid}")
        return ids


class CourseCatalog(BaseModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    courses: list[Course] = Field(min_length=4)

    @field_validator("courses")
    @classmethod
    def course_ids_are_unique(cls, courses: list[Course]) -> list[Course]:
        if len({c.id for c in courses}) != len(courses):
            raise ValueError("course IDs must be unique")
        return courses
