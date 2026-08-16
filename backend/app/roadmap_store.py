"""Persistence and deterministic fallback generation for user roadmaps."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
import httpx

from app.catalog.loader import get_catalog
from app.config import Settings
from app.profile_store import _get_postgrest_headers, _sanitize_supabase_url
from app.roadmap_models import RoadmapResponse, WeeklyPlanItem
from app.task_store import create_roadmap_tasks, task_states_for_roadmap

logger = logging.getLogger(__name__)

# Local storage keeps endpoint tests independent of a configured Supabase project.
_in_memory_roadmaps: dict[tuple[str, str], dict[str, Any]] = {}


def reset_in_memory_roadmap_store() -> None:
    """Clear roadmaps in the local test store."""
    _in_memory_roadmaps.clear()


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Roadmap not found. Create one for this role first.",
    )


def _weekly_plan_for(role_id: str) -> list[WeeklyPlanItem]:
    """Create the fixed fallback plan from the catalog's ordered milestones."""
    role = next((item for item in get_catalog().roles if item.id == role_id), None)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown role_id: {role_id}",
        )

    return [
        WeeklyPlanItem(
            week=milestone.sequence,
            milestone_id=milestone.id,
            title=milestone.title,
            objective=milestone.objective,
            skills=milestone.skills,
            estimated_effort_hours=milestone.estimated_effort_hours,
            practical_task=milestone.practical_task,
            portfolio_deliverable=milestone.portfolio_deliverable,
            resources=[resource.model_dump(mode="json") for resource in milestone.resources],
        )
        for milestone in role.milestones
    ]


def _response_from_row(row: dict[str, Any], user_id: str, settings: Settings) -> RoadmapResponse:
    tasks_by_milestone = task_states_for_roadmap(
        user_id=user_id,
        roadmap_id=row["id"],
        settings=settings,
    )
    weekly_plan = [
        {
            **item,
            "task_id": tasks_by_milestone.get(item["milestone_id"], {}).get("id"),
            "completed": tasks_by_milestone.get(item["milestone_id"], {}).get("completed", False),
        }
        for item in row["weekly_plan"]
    ]
    return RoadmapResponse(
        role_id=row["role_id"],
        weekly_plan=weekly_plan,
        generation_mode=row["generation_mode"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def upsert_roadmap(user_id: str, role_id: str, settings: Settings) -> RoadmapResponse:
    """Generate and persist a deterministic fallback roadmap for the caller."""
    weekly_plan = _weekly_plan_for(role_id)
    now = datetime.now(timezone.utc)
    stored_row: dict[str, Any] = {
        "user_id": user_id,
        "role_id": role_id,
        "weekly_plan": [
            item.model_dump(mode="json", exclude={"task_id", "completed"})
            for item in weekly_plan
        ],
        "generation_mode": "fallback",
        "updated_at": now.isoformat(),
    }

    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        headers = {
            **_get_postgrest_headers(settings),
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{base_url}/rest/v1/roadmaps?on_conflict=user_id,role_id",
                    headers=headers,
                    json=stored_row,
                )
            if response.status_code not in (200, 201):
                logger.error("Supabase roadmap upsert failed with status %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error during roadmap upsert.",
                )
            rows = response.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database did not return the saved roadmap.",
                )
            stored_row = rows[0]
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error while saving roadmap.",
            )
    else:
        previous = _in_memory_roadmaps.get((user_id, role_id))
        stored_row["id"] = previous["id"] if previous else str(uuid4())
        stored_row["created_at"] = previous["created_at"] if previous else now.isoformat()

    _in_memory_roadmaps[(user_id, role_id)] = stored_row
    create_roadmap_tasks(
        user_id=user_id,
        roadmap_id=stored_row["id"],
        weekly_plan=weekly_plan,
        settings=settings,
    )
    return _response_from_row(stored_row, user_id=user_id, settings=settings)


def get_roadmap(user_id: str, role_id: str, settings: Settings) -> RoadmapResponse:
    """Return only the requested user's persisted roadmap for one catalog role."""
    # Reject bad role IDs consistently for GET as well as POST.
    _weekly_plan_for(role_id)

    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{base_url}/rest/v1/roadmaps?user_id=eq.{user_id}&role_id=eq.{role_id}&select=*",
                    headers=_get_postgrest_headers(settings),
                )
            if response.status_code == 200:
                rows = response.json()
                if not rows:
                    raise _not_found()
                return _response_from_row(rows[0], user_id=user_id, settings=settings)
            if response.status_code == 404:
                raise _not_found()
            logger.error("Supabase roadmap get failed with status %d: %s", response.status_code, response.text)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error while fetching roadmap.",
            )
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error while fetching roadmap.",
            )

    stored_row = _in_memory_roadmaps.get((user_id, role_id))
    if stored_row is None:
        raise _not_found()
    return _response_from_row(stored_row, user_id=user_id, settings=settings)
