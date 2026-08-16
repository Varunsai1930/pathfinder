"""API models for milestone task completion."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TaskCompletionPayload(BaseModel):
    completed: bool


class NextAction(BaseModel):
    milestone_id: str | None
    task_label: str | None
    message: str


class TaskResponse(BaseModel):
    id: UUID
    roadmap_id: UUID
    milestone_id: str
    task_label: str
    completed: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskUpdateResponse(BaseModel):
    task: TaskResponse
    next_action: NextAction
