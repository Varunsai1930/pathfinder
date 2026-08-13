from fastapi import APIRouter

from app.catalog.assessment_loader import get_assessment_catalog
from app.catalog.loader import get_catalog
from app.catalog.models import AssessmentCatalog, Catalog

router = APIRouter(prefix="/api/v1")


@router.get("/catalog/roles", response_model=Catalog, tags=["catalog"])
def list_roles() -> Catalog:
    """Return the validated static catalog used by later matching endpoints."""
    return get_catalog()


@router.get("/assessment", response_model=AssessmentCatalog, tags=["catalog"])
def get_assessment() -> AssessmentCatalog:
    """Return questions and profile skill options used to create a user profile."""
    return get_assessment_catalog()
