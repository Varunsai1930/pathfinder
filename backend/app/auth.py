"""Supabase JWT verification as a FastAPI dependency."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer()


def _decode_jwt(token: str, settings: Settings) -> dict:
    """Decode and verify a Supabase-issued JWT.

    Imported lazily so the ``jwt`` package is only required at call time,
    keeping catalog-only tests fast.
    """
    import jwt  # PyJWT

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
    return payload


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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token does not contain a user identity.")
    return user_id
