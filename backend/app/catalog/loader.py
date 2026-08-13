import json
from functools import lru_cache
from pathlib import Path

from app.catalog.models import Catalog


CATALOG_PATH = Path(__file__).with_name("roles.v1.json")


@lru_cache
def get_catalog() -> Catalog:
    """Load and validate the curated role catalog once per process."""
    with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        return Catalog.model_validate(json.load(catalog_file))
