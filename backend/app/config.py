"""Central settings. Loaded once and cached so every module shares one instance."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Data providers (free tiers — see README for signup links)
    fred_api_key: str = ""
    twelvedata_api_key: str = ""
    currents_api_key: str = ""

    # Shared secret checked on POST /*/refresh so GitHub Actions (and only
    # GitHub Actions) can trigger background refreshes. Also doubles as the
    # keep-warm ping that stops Render's free web service from sleeping and
    # Supabase's free project from pausing after 7 idle days.
    refresh_token: str = "change-me"

    cache_ttl_seconds: int = 900  # 15 minutes


@lru_cache
def get_settings() -> Settings:
    return Settings()
