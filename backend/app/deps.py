"""Shared FastAPI dependencies."""
from fastapi import Header, HTTPException

from app.config import get_settings


async def verify_refresh_token(x_refresh_token: str = Header(default="")) -> None:
    """Guards every POST /*/refresh endpoint.

    Called by .github/workflows/scheduled-refresh.yml with a secret stored
    in the repo's GitHub Actions secrets — never commit the real value.
    Without this, anyone who finds your backend URL could trigger refreshes
    and burn through your FRED / data-provider rate limits.
    """
    settings = get_settings()
    if not settings.refresh_token or x_refresh_token != settings.refresh_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Refresh-Token header")
