"""API response models for persisted fallback roadmaps."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class RoadmapResource(BaseModel):
    title: str
    url: HttpUrl
    provider: str


class WeeklyPlanItem(BaseModel):
    """One catalog milestone scheduled in the deterministic fallback plan."""

    week: int = Field(ge=1, le=5)
    milestone_id: str
    title: str
    objective: str
    skills: list[str]
    estimated_effort_hours: int = Field(ge=1)
    practical_task: str
    portfolio_deliverable: str
    resources: list[RoadmapResource]
    task_id: UUID | None = None
    completed: bool = False
    personalized_focus: str = ""


class RoadmapResponse(BaseModel):
    role_id: str
    weekly_plan: list[WeeklyPlanItem] = Field(min_length=5, max_length=5)
    generation_mode: Literal["fallback", "llm"]
    adaptation_note: str = ""
    created_at: datetime
    updated_at: datetime
