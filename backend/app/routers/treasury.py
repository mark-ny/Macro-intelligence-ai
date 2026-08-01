from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.models.schemas import RefreshResult, YieldCurveResponse, YieldHistoryPoint
from app.services import treasury_service

router = APIRouter()


@router.get("/yield-curve", response_model=YieldCurveResponse)
async def yield_curve():
    """Latest 3M/2Y/5Y/10Y/30Y par yields plus the 10Y-2Y and 10Y-3M spreads,
    including whether the curve is currently inverted."""
    try:
        return await treasury_service.get_yield_curve()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load yield curve: {exc}") from exc


@router.get("/history", response_model=list[YieldHistoryPoint])
async def history(
    series: str = Query("10Y", pattern="^(3M|2Y|5Y|10Y|30Y|10Y2Y|10Y3M)$"),
    days: int = Query(180, ge=7, le=1825),
):
    """Historical daily values for one series, for charting."""
    try:
        return await treasury_service.get_yield_history(series=series, days=days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load yield history: {exc}") from exc


@router.post("/refresh", response_model=RefreshResult, dependencies=[Depends(verify_refresh_token)])
async def manual_refresh():
    """Pull fresh data from FRED into Supabase. Requires X-Refresh-Token.
    Called by the GitHub Actions scheduled workflow — see
    .github/workflows/scheduled-refresh.yml."""
    return await treasury_service.refresh_treasury_data()
