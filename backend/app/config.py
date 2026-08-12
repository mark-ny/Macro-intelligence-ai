"""Central settings. Loaded once and cached so every module shares one instance."""
import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Render env vars are plain strings. Accept either a JSON array
        ('["https://a.com","https://b.com"]') or a plain comma-separated
        list ('https://a.com,https://b.com') so a misformatted env var
        can't crash startup — it used to require strict JSON and raise a
        pydantic ValidationError before the app ever got a chance to run."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Data providers (free tiers — see README for signup links)
    fred_api_key: str = ""
    twelvedata_api_key: str = ""
    currents_api_key: str = ""

    # AI assistant (chat widget) — Gemini Flash via the Google GenAI API.
    # Empty string disables the widget gracefully (see chat_service.py)
    # instead of crashing startup.
    gemini_api_key: str = ""

    # Shared secret checked on POST /*/refresh so GitHub Actions (and only
    # GitHub Actions) can trigger background refreshes. Also doubles as the
    # keep-warm ping that stops Render's free web service from sleeping and
    # Supabase's free project from pausing after 7 idle days.
    refresh_token: str = "change-me"

    cache_ttl_seconds: int = 900  # 15 minutes


@lru_cache
def get_settings() -> Settings:
    return Settings()
