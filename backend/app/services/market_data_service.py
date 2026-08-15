"""Shared market data store.

This is the one place that talks to Twelve Data for OHLC bars — ICT
analysis, Historical Learning, and every Top-Down Analysis calculation
(seasonality, correlation, IPDA ranges) all read the same persisted
market_prices table instead of each hitting the API separately. That
used to be two separate live-fetch paths (ICT and History); consolidating
them here directly serves the project's "minimize duplicate API
requests" goal now that two more features need the same bars.
"""
from datetime import datetime, timedelta, timezone

import httpx

from app.cache import ttl_cache
from app.config import get_settings
from app.database import get_supabase

TIME_SERIES_URL = "https://api.twelvedata.com/time_series"

ASSET_SYMBOLS: dict[str, str] = {
    "XAUUSD": "XAU/USD",
    "NQ": "QQQ",  # proxy — real NQ futures data is a paid feed everywhere we checked
}


async def fetch_daily_bars(asset: str, outputsize: int = 150) -> list[dict]:
    settings = get_settings()
    if not settings.twelvedata_api_key:
        raise RuntimeError("TWELVEDATA_API_KEY is not set — see README > Local development.")
    if asset not in ASSET_SYMBOLS:
        raise ValueError(f"Unknown asset '{asset}'. Valid: {sorted(ASSET_SYMBOLS)}")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            TIME_SERIES_URL,
            params={
                "symbol": ASSET_SYMBOLS[asset],
                "interval": "1day",
                "outputsize": outputsize,
                "apikey": settings.twelvedata_api_key,
            },
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("status") == "error":
        raise RuntimeError(f"Twelve Data error: {payload.get('message')}")

    bars = [
        {
            "datetime": v["datetime"],
            "open": float(v["open"]),
            "high": float(v["high"]),
            "low": float(v["low"]),
            "close": float(v["close"]),
        }
        for v in payload.get("values", [])
    ]
    bars.sort(key=lambda b: b["datetime"])  # Twelve Data returns newest-first; we want ascending
    return bars


async def refresh_market_prices(outputsize: int = 1500) -> dict:
    """~6 years of daily bars per asset (enough for meaningful seasonality),
    upserted into market_prices. Everything else in this file and in
    ict_service/history_service/topdown/short_term reads from that table."""
    supabase = get_supabase()
    rows_total = 0
    errors: dict[str, str] = {}

    for asset in ASSET_SYMBOLS:
        try:
            bars = await fetch_daily_bars(asset, outputsize=outputsize)
        except Exception as exc:  # noqa: BLE001
            errors[asset] = str(exc)
            continue

        rows = [
            {"asset": asset, "date": b["datetime"][:10], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"]}
            for b in bars
        ]
        for i in range(0, len(rows), 500):
            supabase.table("market_prices").upsert(rows[i : i + 500], on_conflict="asset,date").execute()
        rows_total += len(rows)

    return {"rows_upserted": rows_total, "assets_with_errors": errors}


@ttl_cache(seconds=1800)
async def get_stored_bars(asset: str, days_back: int | None = None) -> list[dict]:
    """Ascending-by-date bars from Supabase, shaped like fetch_daily_bars()
    so every existing consumer of that shape keeps working unchanged."""
    supabase = get_supabase()
    query = supabase.table("market_prices").select("date, open, high, low, close").eq("asset", asset)
    if days_back is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        query = query.gte("date", cutoff)
    result = query.order("date").execute()
    return [
        {"datetime": r["date"], "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"]}
        for r in result.data
    ]


def resample_bars(bars: list[dict], period: str) -> list[dict]:
    """Aggregates ascending daily bars into weekly ('1W'), monthly ('1M'),
    or quarterly ('1Q') OHLC — used by the Intermediate perspective's
    top-down bias, the Short-Term perspective's previous-week/month
    reference levels, and Open Float's Quarterly Shift analysis, so all
    three stay consistent with each other by construction."""
    from collections import defaultdict as _defaultdict

    if period == "1D":
        return bars

    def key_fn(d: datetime):
        if period == "1W":
            return d.isocalendar()[:2]
        if period == "1Q":
            return (d.year, (d.month - 1) // 3)  # calendar quarter, not a candle count
        return (d.year, d.month)

    groups: dict[tuple, list[dict]] = _defaultdict(list)
    for bar in bars:
        date = datetime.strptime(bar["datetime"][:10], "%Y-%m-%d")
        groups[key_fn(date)].append(bar)

    resampled = []
    for key in sorted(groups):
        group = groups[key]
        resampled.append({
            "datetime": group[-1]["datetime"],
            "open": group[0]["open"],
            "high": max(b["high"] for b in group),
            "low": min(b["low"] for b in group),
            "close": group[-1]["close"],
        })
    return resampled
