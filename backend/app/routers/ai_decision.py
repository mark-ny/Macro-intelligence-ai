from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import ai_decision_service

router = APIRouter()


@router.get("/latest")
async def latest(asset: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$")):
    try:
        return await ai_decision_service.get_latest_decision(asset=asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load decision: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    """Recomputes and stores a new decision for every asset. Cheap and
    deterministic — safe to call as often as the underlying data changes."""
    return await ai_decision_service.refresh_ai_decisions()
