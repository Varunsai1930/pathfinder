"""Persistence and next-action calculation for roadmap milestone tasks."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
import httpx

from app.catalog.loader import get_catalog
from app.config import Settings
from app.profile_store import _get_postgrest_headers, _sanitize_supabase_url
from app.roadmap_models import WeeklyPlanItem
from app.task_models import NextAction, TaskResponse, TaskUpdateResponse

logger = logging.getLogger(__name__)

_in_memory_tasks: dict[str, dict[str, Any]] = {}


def reset_in_memory_task_store() -> None:
    """Clear tasks in the local test store."""
    _in_memory_tasks.clear()


def task_ids_for_roadmap_for_test(user_id: str, roadmap_id: str) -> list[str]:
    """Return ordered local task IDs for endpoint tests."""
    return [
        task_id
        for task_id, row in sorted(
            _in_memory_tasks.items(), key=lambda item: _milestone_sequence(item[1]["milestone_id"])
        )
        if row["user_id"] == user_id and row["roadmap_id"] == roadmap_id
    ]


def task_states_for_roadmap(
    user_id: str,
    roadmap_id: str,
    settings: Settings,
) -> dict[str, dict[str, Any]]:
    """Return a task's ID and completion state, keyed by milestone ID."""
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{base_url}/rest/v1/tasks?roadmap_id=eq.{roadmap_id}&user_id=eq.{user_id}&select=id,milestone_id,completed",
                    headers=_get_postgrest_headers(settings),
                )
            if response.status_code != 200:
                logger.error("Supabase task lookup failed with status %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error while fetching roadmap tasks.",
                )
            return {row["milestone_id"]: row for row in response.json()}
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error while fetching roadmap tasks.",
            )

    return {
        task["milestone_id"]: task
        for task in _in_memory_tasks.values()
        if task["user_id"] == user_id and task["roadmap_id"] == roadmap_id
    }


def _milestone_sequence(milestone_id: str) -> int:
    for role in get_catalog().roles:
        for milestone in role.milestones:
            if milestone.id == milestone_id:
                return milestone.sequence
    # Task creation only uses catalog milestones. Keep an unknown persisted value last.
    return 999


def _task_response(row: dict[str, Any]) -> TaskResponse:
    return TaskResponse(
        id=row["id"],
        roadmap_id=row["roadmap_id"],
        milestone_id=row["milestone_id"],
        task_label=row["task_label"],
        completed=row["completed"],
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_roadmap_tasks(
    user_id: str,
    roadmap_id: str,
    weekly_plan: list[WeeklyPlanItem],
    settings: Settings,
) -> None:
    """Ensure a roadmap has one incomplete task for each catalog milestone.

    Existing rows are deliberately retained so refreshing a roadmap never loses
    a user's completion progress.
    """
    task_rows = [
        {
            "user_id": user_id,
            "roadmap_id": roadmap_id,
            "milestone_id": item.milestone_id,
            "task_label": item.title,
            "completed": False,
        }
        for item in weekly_plan
    ]

    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        headers = {
            **_get_postgrest_headers(settings),
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{base_url}/rest/v1/tasks?on_conflict=roadmap_id,milestone_id",
                    headers=headers,
                    json=task_rows,
                )
            if response.status_code not in (200, 201):
                logger.error("Supabase task creation failed with status %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error while creating roadmap tasks.",
                )
            return
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error while creating roadmap tasks.",
            )

    now = datetime.now(timezone.utc).isoformat()
    for row in task_rows:
        if any(
            stored["roadmap_id"] == roadmap_id and stored["milestone_id"] == row["milestone_id"]
            for stored in _in_memory_tasks.values()
        ):
            continue
        task_id = str(uuid4())
        _in_memory_tasks[task_id] = {
            "id": task_id,
            **row,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
        }


def _next_action(tasks: list[dict[str, Any]]) -> NextAction:
    next_task = next(
        (task for task in sorted(tasks, key=lambda item: _milestone_sequence(item["milestone_id"])) if not task["completed"]),
        None,
    )
    if next_task is None:
        return NextAction(
            milestone_id=None,
            task_label=None,
            message="All five roadmap milestones are complete. Great work!",
        )
    return NextAction(
        milestone_id=next_task["milestone_id"],
        task_label=next_task["task_label"],
        message=f"Next: {next_task['task_label']}",
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")


def update_task_completion(
    user_id: str,
    task_id: UUID,
    completed: bool,
    settings: Settings,
) -> TaskUpdateResponse:
    """Update an owned task and return the next unfinished milestone."""
    now = datetime.now(timezone.utc).isoformat()

    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        headers = {
            **_get_postgrest_headers(settings),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.patch(
                    f"{base_url}/rest/v1/tasks?id=eq.{task_id}&user_id=eq.{user_id}",
                    headers=headers,
                    json={
                        "completed": completed,
                        "completed_at": now if completed else None,
                        "updated_at": now,
                    },
                )
                if response.status_code not in (200, 204):
                    logger.error("Supabase task update failed with status %d: %s", response.status_code, response.text)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Database error while updating task.",
                    )
                updated_rows = response.json() if response.content else []
                if not updated_rows:
                    raise _not_found()
                updated = updated_rows[0]
                remaining = client.get(
                    f"{base_url}/rest/v1/tasks?roadmap_id=eq.{updated['roadmap_id']}&user_id=eq.{user_id}&select=*",
                    headers=_get_postgrest_headers(settings),
                )
            if remaining.status_code != 200:
                logger.error("Supabase task lookup failed with status %d: %s", remaining.status_code, remaining.text)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error while calculating next action.",
                )
            return TaskUpdateResponse(task=_task_response(updated), next_action=_next_action(remaining.json()))
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error while updating task.",
            )

    stored = _in_memory_tasks.get(str(task_id))
    if stored is None or stored["user_id"] != user_id:
        raise _not_found()

    stored["completed"] = completed
    stored["completed_at"] = now if completed else None
    stored["updated_at"] = now
    tasks = [
        task
        for task in _in_memory_tasks.values()
        if task["user_id"] == user_id and task["roadmap_id"] == stored["roadmap_id"]
    ]
    return TaskUpdateResponse(task=_task_response(stored), next_action=_next_action(tasks))
