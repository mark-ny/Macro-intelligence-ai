from fastapi import APIRouter, Depends

from app.deps import verify_refresh_token
from app.services import market_data_service

router = APIRouter()


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    """Pulls OHLC bars into market_prices. Must run before ict/refresh,
    history/refresh, and every Top-Down Analysis refresh endpoint, since
    they all read from this table rather than fetching Twelve Data
    themselves — see market_data_service.py docstring."""
    return await market_data_service.refresh_market_prices()
