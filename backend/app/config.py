from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables only."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    pathfinder_env: str = "development"
    pathfinder_cors_origins: str = "http://localhost:5173"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"
    openrouter_api_key: str | None = None
    # Pinned free-tier model with structured-output support (verified
    # https://openrouter.ai/models). Pinned for reproducibility; the
    # auto-router openrouter/free rotates and harms judge evaluation.
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.pathfinder_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
