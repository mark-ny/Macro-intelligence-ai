from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import performance_service

router = APIRouter()


@router.get("/summary")
async def summary(asset: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$")):
    try:
        return await performance_service.get_performance_summary(asset=asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load performance summary: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    return await performance_service.refresh_performance_metrics()
