import json
from functools import lru_cache
from pathlib import Path

from app.catalog.models import CourseCatalog


COURSES_PATH = Path(__file__).with_name("courses.v1.json")


@lru_cache
def get_courses_catalog() -> CourseCatalog:
    """Load and validate the curated course catalog once per process."""
    with COURSES_PATH.open(encoding="utf-8") as f:
        return CourseCatalog.model_validate(json.load(f))
