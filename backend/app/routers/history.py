from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import history_service

router = APIRouter()


@router.get("/outcomes")
async def outcomes(asset: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$"), limit: int = Query(20, ge=1, le=100)):
    try:
        return await history_service.get_outcomes(asset=asset, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load outcomes: {exc}") from exc


@router.get("/win-rate")
async def win_rate(asset: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$")):
    try:
        return await history_service.get_win_rate(asset=asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load win rate: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    """Evaluates decisions old enough to judge — not a data pull, so it's
    cheap to run often."""
    return await history_service.evaluate_pending_decisions()
