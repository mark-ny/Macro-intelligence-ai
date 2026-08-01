from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import ict_service

router = APIRouter()


@router.get("/signals")
async def signals(asset: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$"), limit: int = Query(20, ge=1, le=100)):
    try:
        return await ict_service.get_latest_signals(asset=asset, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load ICT signals: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    return await ict_service.refresh_ict_signals()
