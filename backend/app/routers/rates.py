from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import rates_service

router = APIRouter()


@router.get("/snapshot")
async def snapshot():
    """Fed funds rate, SOFR, and the 2Y-yield-derived rate expectation."""
    try:
        return await rates_service.get_rate_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load rate snapshot: {exc}") from exc


@router.get("/history")
async def history(
    series: str = Query("FEDFUNDS", pattern="^(FEDFUNDS|SOFR)$"),
    days: int = Query(180, ge=7, le=1825),
):
    try:
        return await rates_service.get_rate_history(series=series, days=days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load rate history: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    return await rates_service.refresh_rates_data()
