from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import big_picture_service, intermediate_service, short_term_service

router = APIRouter()

ASSET_PATTERN = "^(XAUUSD|NQ)$"


@router.get("/big-picture")
async def big_picture(asset: str = Query("XAUUSD", pattern=ASSET_PATTERN)):
    """Macro market analysis (inflation regime), interest rate analysis,
    inter-market analysis (commodities + USDX), and seasonal tendencies."""
    try:
        return await big_picture_service.get_big_picture_summary(asset=asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load big-picture view: {exc}") from exc


@router.get("/intermediate")
async def intermediate(asset: str = Query("XAUUSD", pattern=ASSET_PATTERN)):
    """Top-down monthly/weekly/daily structural bias, COT positioning, and
    combined market sentiment."""
    try:
        return await intermediate_service.get_intermediate_summary(asset=asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load intermediate view: {exc}") from exc


@router.get("/short-term")
async def short_term(asset: str = Query("XAUUSD", pattern=ASSET_PATTERN)):
    """Correlation analysis, time/price theory reference levels, and IPDA
    rolling-range positioning."""
    try:
        return await short_term_service.get_short_term_summary(asset=asset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load short-term view: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    """Runs every Top-Down sub-analysis in dependency order. Assumes
    POST /api/market-data/refresh has already run in this cycle — see
    .github/workflows/scheduled-refresh.yml, which always calls market-data
    before top-down."""
    results = {}
    results["cpi"] = await big_picture_service.refresh_cpi_data()
    results["commodity_index"] = await big_picture_service.refresh_commodity_index()
    results["macro_regime"] = await big_picture_service.compute_macro_regime()
    results["seasonality"] = await big_picture_service.refresh_seasonality()
    results["topdown_bias"] = await intermediate_service.refresh_topdown_bias()
    results["cot"] = await intermediate_service.refresh_cot_data()
    results["correlations"] = await short_term_service.compute_correlations()
    results["ipda_ranges"] = await short_term_service.refresh_ipda_ranges()
    return results
