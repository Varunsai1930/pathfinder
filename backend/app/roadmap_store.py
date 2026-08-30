"""Persistence and deterministic fallback generation for user roadmaps."""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.catalog.loader import get_catalog
from app.config import Settings
from app.http_client import pooled_client
from app.matching.models import MatchProfile
from app.matching.service import match_profile
from app.personalization import personalize_roadmap_response
from app.profile_store import (
    _get_postgrest_headers,
    _in_memory_profiles,
    _sanitize_supabase_url,
    get_profile,
)
from app.roadmap_models import RoadmapResponse, WeeklyPlanItem
from app.task_store import create_roadmap_tasks, task_states_for_roadmap

logger = logging.getLogger(__name__)

# Local storage keeps endpoint tests independent of a configured Supabase project.
_in_memory_roadmaps: dict[tuple[str, str], dict[str, Any]] = {}


class _DisplayLayerCache:
    """Bounded in-process memo of personalized roadmap display layers.

    The display layer (fit explanation, adaptation note, per-milestone focus)
    is LLM-personalized; before this memo, *every* GET /roadmaps for a roadmap
    with any completed milestone re-ran OpenRouter — a potential 25s stall per
    page load. Entries are keyed by (user_id, role_id) plus a task-state
    signature: a repeat read with unchanged progress is served from the memo.

    Deliberately in-process and bounded: another worker or a restart costs one
    extra personalization call, never a wrong answer, and a resubmitted profile
    invalidates the user's entries explicitly (see
    invalidate_display_cache_for_user, called from profile_store).
    """

    def __init__(self, max_entries: int = 256) -> None:
        self._entries: OrderedDict[tuple[str, str], tuple[str, RoadmapResponse]] = OrderedDict()
        self._max_entries = max_entries

    def get(self, user_id: str, role_id: str, signature: str) -> RoadmapResponse | None:
        entry = self._entries.get((user_id, role_id))
        if entry is not None and entry[0] == signature:
            self._entries.move_to_end((user_id, role_id))
            return entry[1]
        return None

    def set(self, user_id: str, role_id: str, signature: str, layer: RoadmapResponse) -> None:
        self._entries[(user_id, role_id)] = (signature, layer)
        self._entries.move_to_end((user_id, role_id))
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate_user(self, user_id: str) -> None:
        for key in [key for key in self._entries if key[0] == user_id]:
            del self._entries[key]

    def clear(self) -> None:
        self._entries.clear()


_display_cache = _DisplayLayerCache()


def invalidate_display_cache_for_user(user_id: str) -> None:
    """Drop a user's cached display layers (called when their profile changes)."""
    _display_cache.invalidate_user(user_id)


def _display_signature(response: RoadmapResponse) -> str:
    """The progress state the display layer was personalized against."""
    return json.dumps(
        [
            [item.milestone_id, item.completed, item.time_spent_minutes, item.quiz_score]
            for item in response.weekly_plan
        ]
    )


def reset_in_memory_roadmap_store() -> None:
    """Clear roadmaps in the local test store."""
    _in_memory_roadmaps.clear()
    _display_cache.clear()


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
            "time_spent_minutes": tasks_by_milestone.get(item["milestone_id"], {}).get("time_spent_minutes"),
            "quiz_score": tasks_by_milestone.get(item["milestone_id"], {}).get("quiz_score"),
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


def _with_display_layer(base: RoadmapResponse, layer: RoadmapResponse) -> RoadmapResponse:
    """Apply a known display layer's texts onto a freshly merged base response.

    The base carries authoritative task ids/state; the layer contributes the
    personalized prose (fit explanation, adaptation note, per-milestone focus).
    """
    focus_by_milestone = {
        item.milestone_id: item.personalized_focus for item in layer.weekly_plan
    }
    return base.model_copy(
        update={
            "generation_mode": layer.generation_mode,
            "fit_explanation": layer.fit_explanation,
            "adaptation_note": layer.adaptation_note,
            "weekly_plan": [
                item.model_copy(
                    update={
                        "personalized_focus": focus_by_milestone.get(
                            item.milestone_id, item.personalized_focus
                        )
                    }
                )
                for item in base.weekly_plan
            ],
        }
    )


def _fresh_display_layer(
    response: RoadmapResponse, user_id: str, settings: Settings
) -> RoadmapResponse:
    """Re-personalize once progress exists so pacing reflects real completion state.

    The stored layer is generated at creation time, when nothing is completed;
    returning it verbatim would show an empty adaptation_note next to finished
    milestones. Fresh roadmaps keep the stored layer without another LLM call.

    Memoized on the task-state signature: repeat reads with unchanged progress
    (the common case — a judge clicking between Progress and Dashboard) are
    served without an OpenRouter round-trip. A task toggle or profile
    resubmission changes the signature / clears the memo, so the layer is
    honestly recomputed exactly when the state it describes changes.
    """
    signature = _display_signature(response)
    cached = _display_cache.get(user_id, response.role_id, signature)
    if cached is not None:
        return cached
    if not any(item.completed for item in response.weekly_plan):
        return response
    layer = _personalized_or_fallback_roadmap(response, user_id=user_id, settings=settings)
    _display_cache.set(user_id, response.role_id, signature, layer)
    return layer



def _mark_selected_role(user_id: str, role_id: str, settings: Settings) -> None:
    """Record the learner's most recently explored path on their profile.

    Best-effort: the progress page uses this to track the roadmap the learner
    actually chose (falling back to their top match). Never fails the roadmap.
    """
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        try:
            with pooled_client() as client:
                client.patch(
                    f"{base_url}/rest/v1/profiles?user_id=eq.{user_id}",
                    headers={
                        **_get_postgrest_headers(settings),
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json={"selected_role_id": role_id},
                )
        except Exception as exc:
            logger.info("Selected-role marker skipped: %s", exc)
        return
    stored = _in_memory_profiles.get(user_id)
    if stored is not None:
        stored["selected_role_id"] = role_id


def upsert_roadmap(user_id: str, role_id: str, settings: Settings) -> RoadmapResponse:
    """Persist a deterministic roadmap with an optional validated LLM display layer."""
    weekly_plan = _weekly_plan_for(role_id)
    now = datetime.now(UTC)

    # Check for existing tasks so that re-personalizing a roadmap with progress
    # immediately sends the real completion state to the LLM.
    existing_tasks: dict[str, dict[str, Any]] = {}
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        try:
            with pooled_client() as client:
                resp = client.get(
                    f"{base_url}/rest/v1/roadmaps?user_id=eq.{user_id}&role_id=eq.{role_id}&select=id",
                    headers=_get_postgrest_headers(settings),
                )
                if resp.status_code == 200 and resp.json():
                    existing_roadmap_id = resp.json()[0]["id"]
                    existing_tasks = task_states_for_roadmap(
                        user_id=user_id, roadmap_id=existing_roadmap_id, settings=settings
                    )
        except Exception:
            existing_tasks = {}
    else:
        existing_stored = _in_memory_roadmaps.get((user_id, role_id))
        if existing_stored:
            existing_tasks = task_states_for_roadmap(
                user_id=user_id, roadmap_id=existing_stored["id"], settings=settings
            )

    weekly_plan_with_state = [
        item.model_copy(update={
            "task_id": existing_tasks.get(item.milestone_id, {}).get("id"),
            "completed": existing_tasks.get(item.milestone_id, {}).get("completed", False),
            "time_spent_minutes": existing_tasks.get(item.milestone_id, {}).get("time_spent_minutes"),
            "quiz_score": existing_tasks.get(item.milestone_id, {}).get("quiz_score"),
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
            with pooled_client() as client:
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
            ) from exc
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
    _mark_selected_role(user_id=user_id, role_id=role_id, settings=settings)
    # The layer above was personalized against exactly this task state — seed
    # the memo so the return trip and the next GET stay LLM-free (previously
    # POST /roadmaps ran the LLM twice, and every GET ran it again).
    merged = _response_from_row(stored_row, user_id=user_id, settings=settings)
    _display_cache.set(
        user_id,
        role_id,
        _display_signature(merged),
        _with_display_layer(merged, personalized),
    )
    return _fresh_display_layer(
        merged,
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
            with pooled_client() as client:
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
            ) from exc

    stored_row = _in_memory_roadmaps.get((user_id, role_id))
    if stored_row is None:
        raise _not_found()
    return _fresh_display_layer(
        _response_from_row(stored_row, user_id=user_id, settings=settings),
        user_id=user_id,
        settings=settings,
    )
