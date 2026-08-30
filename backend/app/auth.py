"""Supabase JWT verification as a FastAPI dependency."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer()
_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_jwks_client(jwks_url: str, anon_key: str | None = None):
    """Lazily create and cache a PyJWKClient for the given JWKS URL."""
    import jwt  # PyJWT

    headers = {"apikey": anon_key} if anon_key else None
    return jwt.PyJWKClient(jwks_url, headers=headers, cache_jwk_set=True, lifespan=300)


def _decode_jwt(token: str, settings: Settings) -> dict:
    """Decode and verify a Supabase-issued JWT.

    Primary path: JWKS-based RS256/ES256 verification using Supabase's
    published public keys.  Falls back to HS256 with the shared secret
    if JWKS verification fails and a secret is configured.

    Imported lazily so the ``jwt`` package is only required at call time,
    keeping catalog-only tests fast.
    """
    import jwt  # PyJWT

    jwks_url = (
        f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        if settings.supabase_url
        else None
    )

    # --- Primary: JWKS / RS256 / ES256 ---
    jwks_error: Exception | None = None
    if jwks_url:
        try:
            jwks_client = _get_jwks_client(jwks_url, settings.supabase_anon_key)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=settings.supabase_jwt_audience,
            )
        except jwt.ExpiredSignatureError:
            # Token is structurally valid but expired — no point falling back.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
            ) from None
        except Exception as exc:
            jwks_error = exc
            _logger.warning(
                "JWKS verification failed, attempting HS256 fallback: %s", exc,
            )

    # --- Fallback: HS256 shared secret (transition period) ---
    if settings.supabase_jwt_secret:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
            ) from None
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {exc}",
            ) from exc

    # --- Neither path succeeded ---
    if jwks_error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {jwks_error}",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No JWT verification method configured.",
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    """Return the authenticated Supabase user ID from a verified JWT.

    The user ID is always derived from the token's ``sub`` claim — never
    from request body data.  Override this dependency in tests via
    ``app.dependency_overrides[get_current_user]``.
    """
    payload = _decode_jwt(credentials.credentials, settings)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain a user identity.",
        )
    return user_id
