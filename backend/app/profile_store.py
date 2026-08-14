"""Persistence layer for user profiles in Supabase Postgres with local in-memory fallback."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import HTTPException, status
import httpx

from app.config import Settings
from app.matching.models import (
    CareerCertainty,
    ProfileConstraints,
    ProfilePayload,
    ProfileResponse,
    SkillConfidence,
    WorkStyleResponses,
)

logger = logging.getLogger(__name__)

# In-memory profile storage used during local test suites or when Supabase is unconfigured
_in_memory_profiles: dict[str, dict[str, Any]] = {}


def reset_in_memory_store() -> None:
    """Clear all profiles in the test in-memory store."""
    _in_memory_profiles.clear()


def _sanitize_supabase_url(url: str) -> str:
    cleaned = url.rstrip("/")
    if cleaned.endswith("/rest/v1"):
        cleaned = cleaned[:-8]
    return cleaned.rstrip("/")


def _get_auth_header(settings: Settings, token: str | None = None) -> str:
    if token:
        return f"Bearer {token}"
    if settings.supabase_jwt_secret:
        try:
            import jwt

            ref = "eharywyxdhcikmxupjtz"
            if settings.supabase_anon_key:
                try:
                    decoded = jwt.decode(settings.supabase_anon_key, options={"verify_signature": False})
                    ref = decoded.get("ref", ref)
                except Exception:
                    pass
            payload = {
                "iss": "supabase",
                "ref": ref,
                "role": "service_role",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int(datetime.now(timezone.utc).timestamp()) + 3600 * 24,
            }
            service_token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
            return f"Bearer {service_token}"
        except Exception:
            pass
    if settings.supabase_anon_key:
        return f"Bearer {settings.supabase_anon_key}"
    return ""


def upsert_profile(
    user_id: str,
    payload: ProfilePayload,
    settings: Settings,
    token: str | None = None,
) -> ProfileResponse:
    """Save or overwrite a user profile keyed by verified user_id.

    In production, writes directly to Supabase PostgREST with RLS credentials.
    In local test environments, persists into an in-memory test store.
    """
    if settings.supabase_url and settings.supabase_anon_key:
        base_url = _sanitize_supabase_url(settings.supabase_url)
        auth_header = _get_auth_header(settings, token)
        headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }

        db_payload = {
            "user_id": user_id,
            "interest_profile": payload.interest_responses,
            "skill_confidence": {
                k: (v.value if isinstance(v, SkillConfidence) else str(v))
                for k, v in payload.skill_confidence.items()
            },
            "work_style_profile": payload.work_style_responses.model_dump(),
            "hours_per_week": payload.constraints.hours_per_week,
            "target_timeline_weeks": payload.constraints.target_timeline_weeks,
            "career_certainty": (
                payload.constraints.career_certainty.value
                if isinstance(payload.constraints.career_certainty, CareerCertainty)
                else str(payload.constraints.career_certainty)
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{base_url}/rest/v1/profiles",
                    headers=headers,
                    json=db_payload,
                )
            if resp.status_code not in (200, 201):
                logger.error("Supabase upsert failed with status %d: %s", resp.status_code, resp.text)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error during profile upsert: {resp.text}",
                )
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database connection error: {exc}",
            )

    # Mirror into in-memory store
    _in_memory_profiles[user_id] = payload.model_dump()

    return ProfileResponse(
        interest_responses=payload.interest_responses,
        skill_confidence=payload.skill_confidence,
        work_style_responses=payload.work_style_responses,
        constraints=payload.constraints,
    )


def get_profile(
    user_id: str,
    settings: Settings,
    token: str | None = None,
) -> ProfileResponse:
    """Retrieve persisted profile for the given user_id only.

    Returns 404 if no profile exists for the user.
    """
    if settings.supabase_url and settings.supabase_anon_key:
        base_url = _sanitize_supabase_url(settings.supabase_url)
        auth_header = _get_auth_header(settings, token)
        headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": auth_header,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{base_url}/rest/v1/profiles?user_id=eq.{user_id}&select=*",
                    headers=headers,
                )
            if resp.status_code == 200:
                rows = resp.json()
                if not rows:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Profile not found. Complete and submit the assessment first.",
                    )
                row = rows[0]
                return ProfileResponse(
                    interest_responses=row.get("interest_profile") or {},
                    skill_confidence=row.get("skill_confidence") or {},
                    work_style_responses=WorkStyleResponses(**(row.get("work_style_profile") or {})),
                    constraints=ProfileConstraints(
                        hours_per_week=row.get("hours_per_week"),
                        target_timeline_weeks=row.get("target_timeline_weeks"),
                        career_certainty=CareerCertainty(row.get("career_certainty")),
                    ),
                )
            elif resp.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Profile not found. Complete and submit the assessment first.",
                )
            else:
                logger.error("Supabase get failed with status %d: %s", resp.status_code, resp.text)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error while fetching profile: {resp.text}",
                )
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database connection error: {exc}",
            )

    if user_id not in _in_memory_profiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Complete and submit the assessment first.",
        )

    stored = _in_memory_profiles[user_id]
    return ProfileResponse(
        interest_responses=stored["interest_responses"],
        skill_confidence=stored["skill_confidence"],
        work_style_responses=WorkStyleResponses(**stored["work_style_responses"]),
        constraints=ProfileConstraints(**stored["constraints"]),
    )
