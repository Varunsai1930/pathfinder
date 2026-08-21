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
                    f"{base_url}/rest/v1/tasks?roadmap_id=eq.{roadmap_id}&user_id=eq.{user_id}&select=id,milestone_id,completed,time_spent_minutes,quiz_score",
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
        time_spent_minutes=row.get("time_spent_minutes"),
        quiz_score=row.get("quiz_score"),
    )


def _apply_feedback_skill_promotion(
    user_id: str, milestone_id: str, completed: bool, settings: Settings
) -> dict | None:
    """Feedback loop: completing a milestone promotes its skills to practised.

    Returns a small progression snapshot for the response, or None if not applied.
    """
    if not completed:
        return None
    # Resolve milestone skills
    milestone_skills: list[str] = []
    for role in get_catalog().roles:
        for milestone in role.milestones:
            if milestone.id == milestone_id:
                milestone_skills = list(milestone.skills)
                break
    if not milestone_skills:
        return None

    # In-memory path (tests / no Supabase)
    if not (settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key)):
        try:
            from app.profile_store import _in_memory_profiles
        except ImportError:
            return None
        stored = _in_memory_profiles.get(user_id)
        if not stored:
            return None
        sc = stored.get("skill_confidence") or {}
        upgraded: list[str] = []
        for sid in milestone_skills:
            current = sc.get(sid, "none")
            # Normalize enum vs string
            cur = current.value if hasattr(current, "value") else str(current)
            if cur in ("none", "aware"):
                sc[sid] = "practised"
                upgraded.append(sid)
        if upgraded:
            stored["skill_confidence"] = sc
        # Build snapshot for UI — recompute implied readiness increment
        return {
            "upgraded_skills": upgraded,
            "milestone_id": milestone_id,
            "message": f"Feedback loop: {', '.join(upgraded)} promoted to practised" if upgraded else "No new skills promoted",
        }

    # Supabase path — try to patch profile row if present
    try:
        from app.profile_store import _get_postgrest_headers, _sanitize_supabase_url

        base_url = _sanitize_supabase_url(settings.supabase_url)
        headers = _get_postgrest_headers(settings)
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{base_url}/rest/v1/profiles?user_id=eq.{user_id}&select=skill_confidence",
                headers=headers,
            )
            if resp.status_code != 200 or not resp.json():
                return None
            row = resp.json()[0]
            sc = row.get("skill_confidence") or {}
            upgraded = []
            for sid in milestone_skills:
                if sc.get(sid) in (None, "none", "aware"):
                    sc[sid] = "practised"
                    upgraded.append(sid)
            if upgraded:
                patch = client.patch(
                    f"{base_url}/rest/v1/profiles?user_id=eq.{user_id}",
                    headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json={"skill_confidence": sc},
                )
                if patch.status_code not in (200, 204):
                    logger.warning("Feedback skill promotion patch failed %s", patch.text)
            return {
                "upgraded_skills": upgraded,
                "milestone_id": milestone_id,
                "message": f"Feedback loop: {', '.join(upgraded)} promoted" if upgraded else "No new skills promoted",
            }
    except Exception as exc:  # Feedback must never break task update
        logger.info("Feedback loop skipped: %s", exc)
        return None


def _telemetry_summary(tasks: list[dict[str, Any]]) -> dict:
    """Summarize learning-pattern telemetry across a roadmap's tasks."""
    completed = [t for t in tasks if t.get("completed")]
    total = len(tasks)
    avg_time = None
    avg_quiz = None
    if completed:
        times = [t.get("time_spent_minutes") for t in completed if isinstance(t.get("time_spent_minutes"), int)]
        quizzes = [t.get("quiz_score") for t in completed if isinstance(t.get("quiz_score"), int)]
        if times:
            avg_time = round(sum(times) / len(times), 1)
        if quizzes:
            avg_quiz = round(sum(quizzes) / len(quizzes), 1)
    # Simple pace insight
    pace_note = ""
    if avg_time is not None:
        # Compare to catalog estimated total
        if avg_time < 60:
            pace_note = "Fast pace — you tend to finish quickly."
        elif avg_time > 180:
            pace_note = "Slower pace — consider breaking tasks into smaller blocks."
        else:
            pace_note = "Steady pace — on track with estimates."
    return {
        "completed_count": len(completed),
        "total_count": total,
        "completion_rate": round(len(completed) / total * 100, 1) if total else 0.0,
        "avg_time_spent_minutes": avg_time,
        "avg_quiz_score": avg_quiz,
        "pace_note": pace_note,
    }


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
            "time_spent_minutes": None,
            "quiz_score": None,
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
    # P2 adaptive hint based on telemetry
    summary = _telemetry_summary(tasks)
    base = f"Next: {next_task['task_label']}"
    extras: list[str] = []
    if summary["avg_quiz_score"] is not None and summary["avg_quiz_score"] < 60:
        extras.append(f"quiz avg {summary['avg_quiz_score']}% — review fundamentals before advancing")
    elif summary["avg_time_spent_minutes"] is not None and summary["avg_time_spent_minutes"] > 180:
        extras.append("pace is slower than estimated — consider smaller blocks")
    # Skill progression hint already via skill_progression, but include pace note if relevant
    message = base + (" — " + " • ".join(extras) if extras else "")
    return NextAction(
        milestone_id=next_task["milestone_id"],
        task_label=next_task["task_label"],
        message=message,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")


def update_task_completion(
    user_id: str,
    task_id: UUID,
    completed: bool,
    settings: Settings,
    time_spent_minutes: int | None = None,
    quiz_score: int | None = None,
) -> TaskUpdateResponse:
    """Update an owned task and return the next unfinished milestone.

    P2 adaptation: persists telemetry and triggers skill-promotion feedback loop.
    """
    now = datetime.now(timezone.utc).isoformat()
    # Validation for telemetry (preserve backward compatibility)
    if time_spent_minutes is not None and not (0 <= time_spent_minutes <= 10080):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="time_spent_minutes must be 0..10080")
    if quiz_score is not None and not (0 <= quiz_score <= 100):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="quiz_score must be 0..100")

    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        headers = {
            **_get_postgrest_headers(settings),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        patch_payload: dict[str, Any] = {
            "completed": completed,
            "completed_at": now if completed else None,
            "updated_at": now,
        }
        if time_spent_minutes is not None:
            patch_payload["time_spent_minutes"] = time_spent_minutes
        if quiz_score is not None:
            patch_payload["quiz_score"] = quiz_score
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.patch(
                    f"{base_url}/rest/v1/tasks?id=eq.{task_id}&user_id=eq.{user_id}",
                    headers=headers,
                    json=patch_payload,
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
                # Feedback loop on Supabase path as well
                skill_prog_sb = _apply_feedback_skill_promotion(user_id, updated["milestone_id"], completed, settings)
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
            tasks_data = remaining.json()
            return TaskUpdateResponse(
                task=_task_response(updated),
                next_action=_next_action(tasks_data),
                skill_progression=skill_prog_sb,
                telemetry_summary=_telemetry_summary(tasks_data),
            )
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
    if time_spent_minutes is not None:
        stored["time_spent_minutes"] = time_spent_minutes
    if quiz_score is not None:
        stored["quiz_score"] = quiz_score
    # Feedback loop: promote skills linked to this milestone
    skill_prog = _apply_feedback_skill_promotion(user_id, stored["milestone_id"], completed, settings)
    tasks = [
        task
        for task in _in_memory_tasks.values()
        if task["user_id"] == user_id and task["roadmap_id"] == stored["roadmap_id"]
    ]
    return TaskUpdateResponse(
        task=_task_response(stored),
        next_action=_next_action(tasks),
        skill_progression=skill_prog,
        telemetry_summary=_telemetry_summary(tasks),
    )
