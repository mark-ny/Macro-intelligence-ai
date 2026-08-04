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
    """Runs the ICT detector suite, persists signals, then grades any
    reinforcement-learning predictions that are now old enough to judge.
    Both steps live behind this one endpoint because GitHub Actions'
    scheduled-refresh workflow — the reliable trigger, per scheduler.py —
    calls each module's /refresh endpoint once; the in-process scheduler
    still runs them as two separate steps for its own defense-in-depth
    pass."""
    refresh_result = await ict_service.refresh_ict_signals()
    learning_result = await ict_service.evaluate_learning_records()
    return {**refresh_result, "reinforcement_learning": learning_result}
