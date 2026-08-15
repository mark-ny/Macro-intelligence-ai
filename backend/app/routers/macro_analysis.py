from fastapi import APIRouter, HTTPException, Query

from app.services import open_float_service

router = APIRouter()


@router.get("/open-float")
async def open_float(asset: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$")):
    try:
        return await open_float_service.get_open_float_analysis(asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to compute Open Float analysis: {exc}") from exc
