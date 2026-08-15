from fastapi import APIRouter, HTTPException, Query

from app.services import ipda_service

router = APIRouter()


@router.get("/data-ranges")
async def data_ranges(symbol: str = Query("XAUUSD", pattern="^(XAUUSD|NQ)$")):
    try:
        return await ipda_service.get_ipda_data_ranges(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to compute IPDA data ranges: {exc}") from exc
