import json
from functools import lru_cache
from pathlib import Path

from app.catalog.models import AssessmentCatalog

ASSESSMENT_PATH = Path(__file__).with_name("assessment.v1.json")


@lru_cache
def get_assessment_catalog() -> AssessmentCatalog:
    """Load the original Pathfinder assessment and shared skill taxonomy."""
    with ASSESSMENT_PATH.open(encoding="utf-8") as assessment_file:
        return AssessmentCatalog.model_validate(json.load(assessment_file))
