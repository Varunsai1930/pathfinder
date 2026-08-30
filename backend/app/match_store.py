"""Persistence for computed match results so repeat reads never recompute."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.http_client import pooled_client
from app.matching.models import MatchResponse
from app.profile_store import _get_postgrest_headers, _sanitize_supabase_url

logger = logging.getLogger(__name__)

# In-memory match cache for tests / unconfigured Supabase. Production writes
# go to Supabase only — mirroring here would grow a long-lived process
# without bound.
_in_memory_matches: dict[str, dict[str, Any]] = {}


def reset_in_memory_match_store() -> None:
    """Clear cached match results in the test in-memory store."""
    _in_memory_matches.clear()


def persist_match_result(
    user_id: str,
    response: MatchResponse,
    profile_updated_at: str | None,
    settings: Settings,
) -> None:
    """Cache the latest match so GET /match can serve it verbatim.

    Best-effort by design: a persistence failure never fails the POST — the
    caller still returns the freshly computed response, and the next GET
    simply falls back to recompute.
    """
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        headers = {
            **_get_postgrest_headers(settings),
            "Content-Type": "application/json",
            "Prefer": "return=minimal,resolution=merge-duplicates",
        }
        rows = [
            {
                "user_id": user_id,
                "role_id": recommendation.role_id,
                "total_score": round(recommendation.pathfinder_fit_score, 2),
                "score_breakdown": {
                    "profile_updated_at": profile_updated_at,
                    "response": response.model_dump(mode="json"),
                },
            }
            for recommendation in response.recommendations
        ]
        try:
            # Single-statement upsert on the (user_id, role_id) unique index
            # (20260831000000_recommendations_unique.sql) — replaces the old
            # delete-then-insert round trip. on_conflict must name that index
            # explicitly: PostgREST otherwise targets the surrogate id PK,
            # which never conflicts, so a second write would 409 and the
            # cache would stay write-once per user.
            with pooled_client() as client:
                created = client.post(
                    f"{base_url}/rest/v1/recommendations?on_conflict=user_id,role_id",
                    headers=headers,
                    json=rows,
                )
            if created.status_code not in (200, 201):
                logger.warning("Match result persistence failed %d: %s", created.status_code, created.text)
        except httpx.RequestError as exc:
            logger.warning("Match result persistence skipped: %s", exc)
        return

    _in_memory_matches[user_id] = {
        "profile_updated_at": profile_updated_at,
        "response": response.model_dump(mode="json"),
    }


def load_match_result(
    user_id: str,
    profile_updated_at: str | None,
    settings: Settings,
) -> MatchResponse | None:
    """Return the persisted match only when computed from this exact profile version."""
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        base_url = _sanitize_supabase_url(settings.supabase_url)
        try:
            with pooled_client() as client:
                resp = client.get(
                    f"{base_url}/rest/v1/recommendations?user_id=eq.{user_id}&select=score_breakdown&limit=1",
                    headers=_get_postgrest_headers(settings),
                )
        except httpx.RequestError as exc:
            logger.warning("Match result lookup skipped: %s", exc)
            return None
        if resp.status_code != 200 or not resp.json():
            return None
        stored = resp.json()[0].get("score_breakdown") or {}
    else:
        stored = _in_memory_matches.get(user_id)
        if stored is None:
            return None

    if stored.get("profile_updated_at") != profile_updated_at:
        return None
    try:
        return MatchResponse.model_validate(stored["response"])
    except Exception as exc:  # Corrupt cache must degrade to recompute, never 500.
        logger.warning("Persisted match result failed validation; recomputing: %s", exc)
        return None
