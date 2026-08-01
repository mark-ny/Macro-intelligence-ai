from fastapi import APIRouter, Depends

from app.deps import verify_refresh_token
from app.services import notifications_service

router = APIRouter()


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    """Generates notifications (curve inversions, decision changes, upcoming
    high-impact releases). Listing/marking-read happens directly from the
    frontend against Supabase — see notifications_service.py docstring."""
    return await notifications_service.refresh_notifications()
