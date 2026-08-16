from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.catalog.assessment_loader import get_assessment_catalog
from app.catalog.loader import get_catalog
from app.catalog.models import AssessmentCatalog, Catalog
from app.config import Settings, get_settings
from app.matching.models import (
    MatchProfile,
    MatchResponse,
    ProfilePayload,
    ProfileResponse,
)
from app.matching.service import match_profile
from app.profile_store import get_profile, upsert_profile
from app.roadmap_models import RoadmapResponse
from app.roadmap_store import get_roadmap, upsert_roadmap

router = APIRouter(prefix="/api/v1")


@router.get("/catalog/roles", response_model=Catalog, tags=["catalog"])
def list_roles() -> Catalog:
    """Return the validated static catalog used by matching and client UI."""
    return get_catalog()


@router.get("/catalog/assessment", response_model=AssessmentCatalog, tags=["catalog"])
def get_assessment() -> AssessmentCatalog:
    """Return questions and profile skill options used to create a user profile."""
    return get_assessment_catalog()


@router.post("/match", response_model=MatchResponse, tags=["matching"])
def match_career_paths(
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MatchResponse:
    """Rank Pathfinder's four supported roles using the user's persisted profile.

    Reads the calling user's saved assessment, runs it through the
    deterministic matching engine, and returns four ranked score breakdowns.
    Returns 404 if the user has not submitted a profile yet.
    """
    stored = get_profile(user_id=user_id, settings=settings)
    profile = MatchProfile(
        interest_responses=stored.interest_responses,
        skill_confidence=stored.skill_confidence,
        work_style_responses=stored.work_style_responses,
    )
    return match_profile(profile)


@router.post("/profile", response_model=ProfileResponse, tags=["profile"])
def save_user_profile(
    profile: ProfilePayload,
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    """Save or update the authenticated user's assessment profile.

    Upserts into Postgres/Supabase keyed by the verified JWT user_id.
    Resubmissions overwrite the existing row without duplicate key errors.
    """
    return upsert_profile(user_id=user_id, payload=profile, settings=settings)


@router.get("/profile", response_model=ProfileResponse, tags=["profile"])
def fetch_user_profile(
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    """Return the persisted assessment profile for the calling user only.

    Returns 404 if the user has not submitted an assessment yet.
    """
    return get_profile(user_id=user_id, settings=settings)


@router.post("/roadmaps/{role_id}", response_model=RoadmapResponse, tags=["roadmaps"])
def create_roadmap(
    role_id: str,
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RoadmapResponse:
    """Create or refresh the user's deterministic fallback roadmap for a catalog role."""
    return upsert_roadmap(user_id=user_id, role_id=role_id, settings=settings)


@router.get("/roadmaps/{role_id}", response_model=RoadmapResponse, tags=["roadmaps"])
def fetch_roadmap(
    role_id: str,
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RoadmapResponse:
    """Return the caller's persisted roadmap for one catalog role, or a clean 404."""
    return get_roadmap(user_id=user_id, role_id=role_id, settings=settings)
