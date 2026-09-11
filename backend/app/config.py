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
    # Comma-separated model fallback chain, tried in order until one succeeds:
    #   OPENROUTER_MODELS=primary-model,secondary-model
    # "openrouter/free" auto-routes across the zero-cost tier; it supports
    # structured output. A previous pin (meta-llama/llama-3.1-8b-instruct:free)
    # was retired from OpenRouter's catalog, so the auto-router is the safe
    # default. Re-pin only after verifying https://openrouter.ai/models.
    openrouter_models: str = "openrouter/free"
    # Legacy single-model setting (OPENROUTER_MODEL). It seeds the whole chain
    # only when OPENROUTER_MODELS was never set, so existing deployments and
    # .env files keep working; the list form always wins when both are present.
    openrouter_model: str | None = None
    # Hard ceiling (seconds) across ALL model attempts behind one request: the
    # budget is split evenly across the chain (one model gets the full 8s, two
    # models get 4s each) so /match never visibly hangs on the LLM leg.
    openrouter_timeout_seconds: float = 8.0

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.pathfinder_cors_origins.split(",") if origin.strip()]

    @property
    def openrouter_model_list(self) -> list[str]:
        """Ordered fallback chain, deduplicated; empty config falls back to the auto-router."""
        if self.openrouter_model and "openrouter_models" not in self.model_fields_set:
            raw = self.openrouter_model
        else:
            raw = self.openrouter_models
        models: list[str] = []
        for model in raw.split(","):
            model = model.strip()
            if model and model not in models:
                models.append(model)
        return models or ["openrouter/free"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
