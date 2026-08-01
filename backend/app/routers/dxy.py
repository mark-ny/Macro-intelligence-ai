from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import dxy_service

router = APIRouter()


@router.get("/snapshot")
async def snapshot():
    """Latest DXY proxy value plus the most recent OLS trend forecast."""
    try:
        return await dxy_service.get_dxy_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load DXY snapshot: {exc}") from exc


@router.get("/history")
async def history(days: int = Query(180, ge=7, le=1825)):
    try:
        return await dxy_service.get_dxy_history(days=days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load DXY history: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    return await dxy_service.refresh_dxy_data()
