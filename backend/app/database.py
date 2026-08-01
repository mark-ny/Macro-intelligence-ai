"""Single shared Supabase client (service-role key — server-side only, never
shipped to the frontend)."""
from functools import lru_cache
from supabase import create_client, Client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY are not set. Copy .env.example to "
            ".env and fill them in (see README > Local development)."
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)
