from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.catalog.assessment_loader import get_assessment_catalog
from app.catalog.loader import get_catalog
from app.catalog.models import AssessmentCatalog, Catalog
from app.matching.models import MatchProfile, MatchResponse
from app.matching.service import match_profile

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
def match_career_paths(profile: MatchProfile, _user_id: str = Depends(get_current_user)) -> MatchResponse:
    """Rank Pathfinder's four supported roles using transparent deterministic scoring."""
    return match_profile(profile)

