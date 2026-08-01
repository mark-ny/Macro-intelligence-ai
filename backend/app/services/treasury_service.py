"""Treasury Intelligence Engine.

Data source: FRED (Federal Reserve Economic Data) — api.stlouisfed.org.
Free, official, no commercial-use restriction, ~120 req/min on a free key.
https://fred.stlouisfed.org/docs/api/api_key.html

Design:
  refresh_treasury_data()  -> background job (called by the scheduler AND by
                               GitHub Actions via POST /api/treasury/refresh).
                               Pulls from FRED, upserts into Supabase.
  get_yield_curve()        -> fast path read from Supabase, TTL-cached.
  get_yield_history()      -> fast path read from Supabase, TTL-cached.

Reads never call FRED directly — they only ever read what the background
job already stored. This keeps the request path fast and immune to FRED
rate limits, and means the frontend still works even if FRED is briefly
down.
"""
from datetime import datetime, timedelta, timezone

import httpx

from app.cache import ttl_cache
from app.config import get_settings
from app.database import get_supabase

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED series IDs. 3M/2Y/5Y/10Y/30Y are par yields; the two spreads are
# FRED's own precomputed series (avoids us subtracting floats ourselves).
TREASURY_SERIES: dict[str, str] = {
    "3M": "DGS3MO",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}
SPREAD_SERIES: dict[str, str] = {
    "10Y2Y": "T10Y2Y",  # classic recession-warning spread
    "10Y3M": "T10Y3M",  # the Fed's own preferred spread
}
ALL_SERIES: dict[str, str] = {**TREASURY_SERIES, **SPREAD_SERIES}


async def _fetch_fred_series(series_id: str, days_back: int = 400) -> list[dict]:
    """Fetch raw observations for one FRED series. FRED marks missing days
    (weekends/holidays) with the string '.', which we drop here."""
    settings = get_settings()
    if not settings.fred_api_key:
        raise RuntimeError("FRED_API_KEY is not set — see README > Local development.")

    start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "series_id": series_id,
        "api_key": settings.fred_api_key,
        "file_type": "json",
        "observation_start": start_date,
        "sort_order": "asc",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(FRED_BASE_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    return [
        {"date": obs["date"], "value": float(obs["value"])}
        for obs in payload.get("observations", [])
        if obs.get("value") not in (None, ".")
    ]


async def refresh_treasury_data(days_back: int = 400) -> dict:
    """Pull every tracked series from FRED and upsert into Supabase.

    Called on a schedule (see app/scheduler.py) and on-demand from
    POST /api/treasury/refresh (used by the GitHub Actions cron — see
    .github/workflows/scheduled-refresh.yml).
    """
    supabase = get_supabase()
    rows: list[dict] = []
    errors: dict[str, str] = {}

    for label, series_id in ALL_SERIES.items():
        try:
            observations = await _fetch_fred_series(series_id, days_back=days_back)
        except Exception as exc:  # noqa: BLE001 — we want to keep going on partial failure
            errors[label] = str(exc)
            continue
        rows.extend(
            {"series": label, "date": obs["date"], "value": obs["value"]}
            for obs in observations
        )

    if rows:
        # 500 rows/request keeps well under Supabase's request size limits
        # for a full year of daily data across seven series.
        for i in range(0, len(rows), 500):
            batch = rows[i : i + 500]
            supabase.table("treasury_yields").upsert(batch, on_conflict="series,date").execute()

    return {"rows_upserted": len(rows), "series_with_errors": errors}


@ttl_cache(seconds=900)
async def get_yield_curve() -> dict:
    """Latest point-in-time yield curve + spreads, read from Supabase."""
    supabase = get_supabase()
    result = (
        supabase.table("treasury_yields")
        .select("series, date, value")
        .order("date", desc=True)
        .limit(len(ALL_SERIES) * 5)  # a few days of buffer per series
        .execute()
    )

    latest_by_series: dict[str, dict] = {}
    for row in result.data:
        series = row["series"]
        if series not in latest_by_series:
            latest_by_series[series] = row

    curve = {k: latest_by_series.get(k, {}).get("value") for k in TREASURY_SERIES}
    spreads = {k: latest_by_series.get(k, {}).get("value") for k in SPREAD_SERIES}
    ten_two = spreads.get("10Y2Y")

    dates = [r["date"] for r in latest_by_series.values() if r.get("date")]

    return {
        "yield_curve": curve,
        "spreads": spreads,
        "inverted": ten_two is not None and ten_two < 0,
        "as_of": max(dates) if dates else None,
    }


@ttl_cache(seconds=900)
async def get_yield_history(series: str = "10Y", days: int = 180) -> list[dict]:
    """Historical series for charting, read from Supabase."""
    if series not in ALL_SERIES:
        raise ValueError(f"Unknown series '{series}'. Valid: {sorted(ALL_SERIES)}")

    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    result = (
        supabase.table("treasury_yields")
        .select("date, value")
        .eq("series", series)
        .gte("date", cutoff)
        .order("date")
        .execute()
    )
    return result.data
