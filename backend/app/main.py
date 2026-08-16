from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.auth import get_current_user
from app.config import Settings, get_settings
from app.matching.models import ProfilePayload, ProfileResponse
from app.profile_store import get_profile, upsert_profile
from app.roadmap_models import RoadmapResponse
from app.roadmap_store import get_roadmap, upsert_roadmap

settings = get_settings()

app = FastAPI(
    title="Pathfinder API",
    version="0.1.0",
    description="Grounded career-path planning API for Indian tech students.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.post("/profile", response_model=ProfileResponse, tags=["profile"], include_in_schema=False)
def save_profile_root(
    profile: ProfilePayload,
    user_id: str = Depends(get_current_user),
    app_settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    return upsert_profile(user_id=user_id, payload=profile, settings=app_settings)


@app.get("/profile", response_model=ProfileResponse, tags=["profile"], include_in_schema=False)
def fetch_profile_root(
    user_id: str = Depends(get_current_user),
    app_settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    return get_profile(user_id=user_id, settings=app_settings)


@app.post("/roadmaps/{role_id}", response_model=RoadmapResponse, tags=["roadmaps"], include_in_schema=False)
def create_roadmap_root(
    role_id: str,
    user_id: str = Depends(get_current_user),
    app_settings: Settings = Depends(get_settings),
) -> RoadmapResponse:
    """Compatibility route for the documented non-versioned roadmap endpoint."""
    return upsert_roadmap(user_id=user_id, role_id=role_id, settings=app_settings)


@app.get("/roadmaps/{role_id}", response_model=RoadmapResponse, tags=["roadmaps"], include_in_schema=False)
def fetch_roadmap_root(
    role_id: str,
    user_id: str = Depends(get_current_user),
    app_settings: Settings = Depends(get_settings),
) -> RoadmapResponse:
    """Compatibility route for the documented non-versioned roadmap endpoint."""
    return get_roadmap(user_id=user_id, role_id=role_id, settings=app_settings)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.pathfinder_env}
