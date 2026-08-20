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
from app.matching.models import MatchProfile
from app.matching.service import match_profile
from app.profile_store import _get_postgrest_headers, _sanitize_supabase_url
from app.profile_store import get_profile
from app.personalization import personalize_roadmap_response
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
        fit_explanation=row.get("fit_explanation", ""),
        adaptation_note=row.get("adaptation_note", ""),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _personalized_or_fallback_roadmap(
    base_roadmap: RoadmapResponse, user_id: str, settings: Settings
) -> RoadmapResponse:
    """Build a validated display layer without ever changing deterministic data."""
    try:
        profile = get_profile(user_id=user_id, settings=settings)
        match = match_profile(
            MatchProfile(
                interest_responses=profile.interest_responses,
                skill_confidence=profile.skill_confidence,
                work_style_responses=profile.work_style_responses,
            )
        )
        recommendation = next(
            (item for item in match.recommendations if item.role_id == base_roadmap.role_id), None
        )
    except Exception as exc:  # Profile/matching failures must not stop roadmap creation.
        logger.info("Roadmap LLM context unavailable; using deterministic fallback: %s", exc)
        profile = None
        recommendation = None
    return personalize_roadmap_response(
        base_roadmap,
        recommendation=recommendation,
        constraints=profile.constraints if profile else None,
        settings=settings,
    )


def _fresh_display_layer(
    response: RoadmapResponse, user_id: str, settings: Settings
) -> RoadmapResponse:
    """Re-personalize once progress exists so pacing reflects real completion state.

    The stored layer is generated at creation time, when nothing is completed;
    returning it verbatim would show an empty adaptation_note next to finished
    milestones. Fresh roadmaps keep the stored layer without another LLM call.
    """
    if not any(item.completed for item in response.weekly_plan):
        return response
    return _personalized_or_fallback_roadmap(response, user_id=user_id, settings=settings)


def upsert_roadmap(user_id: str, role_id: str, settings: Settings) -> RoadmapResponse:
    """Persist a deterministic roadmap with an optional validated LLM display layer."""
    weekly_plan = _weekly_plan_for(role_id)
    now = datetime.now(timezone.utc)

    # Check for existing tasks so that re-personalizing a roadmap with progress
    # immediately sends the real completion state to the LLM.
    existing_tasks: dict[str, dict[str, Any]] = {}
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{base_url}/rest/v1/roadmaps?user_id=eq.{user_id}&role_id=eq.{role_id}&select=id",
                    headers=_get_postgrest_headers(settings),
                )
                if resp.status_code == 200 and resp.json():
                    existing_roadmap_id = resp.json()[0]["id"]
                    existing_tasks = task_states_for_roadmap(user_id=user_id, roadmap_id=existing_roadmap_id, settings=settings)
        except Exception:
            existing_tasks = {}
    else:
        existing_stored = _in_memory_roadmaps.get((user_id, role_id))
        if existing_stored:
            existing_tasks = task_states_for_roadmap(user_id=user_id, roadmap_id=existing_stored["id"], settings=settings)

    weekly_plan_with_state = [
        item.model_copy(update={
            "task_id": existing_tasks.get(item.milestone_id, {}).get("id"),
            "completed": existing_tasks.get(item.milestone_id, {}).get("completed", False),
        })
        for item in weekly_plan
    ]

    personalized = _personalized_or_fallback_roadmap(
        RoadmapResponse(
            role_id=role_id,
            weekly_plan=weekly_plan_with_state,
            generation_mode="fallback",
            created_at=now,
            updated_at=now,
        ),
        user_id=user_id,
        settings=settings,
    )
    stored_row: dict[str, Any] = {
        "user_id": user_id,
        "role_id": role_id,
        "weekly_plan": [
            item.model_dump(mode="json", exclude={"task_id", "completed"})
            for item in personalized.weekly_plan
        ],
        "generation_mode": personalized.generation_mode,
        "fit_explanation": personalized.fit_explanation,
        "adaptation_note": personalized.adaptation_note,
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
        # Local persistence only; Supabase writes must not mirror into memory.
        _in_memory_roadmaps[(user_id, role_id)] = stored_row

    create_roadmap_tasks(
        user_id=user_id,
        roadmap_id=stored_row["id"],
        weekly_plan=weekly_plan,
        settings=settings,
    )
    return _fresh_display_layer(
        _response_from_row(stored_row, user_id=user_id, settings=settings),
        user_id=user_id,
        settings=settings,
    )


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
                return _fresh_display_layer(
                    _response_from_row(rows[0], user_id=user_id, settings=settings),
                    user_id=user_id,
                    settings=settings,
                )
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
    return _fresh_display_layer(
        _response_from_row(stored_row, user_id=user_id, settings=settings),
        user_id=user_id,
        settings=settings,
    )
