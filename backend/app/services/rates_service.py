"""Interest Rate Intelligence Engine.

Data source: FRED, same as Treasury.
  DFF    - Effective Federal Funds Rate (daily)
  SOFR   - Secured Overnight Financing Rate (daily)

Rate expectations: CME FedWatch (the usual source for fed-funds-futures-
implied odds) has no free public API, so instead of faking an "implied
probability" we compute an honest, well-known proxy: comparing the current
2Y Treasury yield (already collected by the Treasury module — reused
directly from the treasury_yields table rather than re-fetched) against
the effective funds rate. The 2Y yield reflects the market's average
expected funds rate over the next two years, so:
  2Y meaningfully below Fed Funds  -> market is pricing in net rate cuts
  2Y meaningfully above Fed Funds  -> market is pricing in net rate hikes
  otherwise                        -> market expects rates roughly steady
"""
from datetime import datetime, timedelta, timezone

from app.cache import ttl_cache
from app.database import get_supabase
from app.services.treasury_service import _fetch_fred_series

RATE_SERIES: dict[str, str] = {
    "FEDFUNDS": "DFF",
    "SOFR": "SOFR",
}

# How far the 2Y yield has to sit from the funds rate, in percentage
# points, before we call it a directional expectation rather than "steady".
EXPECTATION_THRESHOLD_PP = 0.25


async def refresh_rates_data(days_back: int = 400) -> dict:
    supabase = get_supabase()
    rows: list[dict] = []
    errors: dict[str, str] = {}

    for label, series_id in RATE_SERIES.items():
        try:
            observations = await _fetch_fred_series(series_id, days_back=days_back)
        except Exception as exc:  # noqa: BLE001
            errors[label] = str(exc)
            continue
        rows.extend(
            {"series": label, "date": obs["date"], "value": obs["value"]}
            for obs in observations
        )

    if rows:
        for i in range(0, len(rows), 500):
            supabase.table("interest_rates").upsert(
                rows[i : i + 500], on_conflict="series,date"
            ).execute()

    return {"rows_upserted": len(rows), "series_with_errors": errors}


def _classify_expectation(funds_rate: float, two_year_yield: float) -> str:
    diff = two_year_yield - funds_rate
    if diff <= -EXPECTATION_THRESHOLD_PP:
        return "cuts_expected"
    if diff >= EXPECTATION_THRESHOLD_PP:
        return "hikes_expected"
    return "steady"


@ttl_cache(seconds=900)
async def get_rate_snapshot() -> dict:
    supabase = get_supabase()

    rates_result = (
        supabase.table("interest_rates")
        .select("series, date, value")
        .order("date", desc=True)
        .limit(len(RATE_SERIES) * 5)
        .execute()
    )
    latest: dict[str, dict] = {}
    for row in rates_result.data:
        if row["series"] not in latest:
            latest[row["series"]] = row

    funds_rate = latest.get("FEDFUNDS", {}).get("value")
    sofr = latest.get("SOFR", {}).get("value")

    two_year_result = (
        supabase.table("treasury_yields")
        .select("date, value")
        .eq("series", "2Y")
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    two_year_yield = two_year_result.data[0]["value"] if two_year_result.data else None

    expectation = (
        _classify_expectation(funds_rate, two_year_yield)
        if funds_rate is not None and two_year_yield is not None
        else None
    )

    dates = [r["date"] for r in latest.values() if r.get("date")]

    return {
        "fed_funds_rate": funds_rate,
        "sofr": sofr,
        "two_year_yield": two_year_yield,
        "expectation": expectation,
        "as_of": max(dates) if dates else None,
    }


@ttl_cache(seconds=900)
async def get_rate_history(series: str = "FEDFUNDS", days: int = 180) -> list[dict]:
    if series not in RATE_SERIES:
        raise ValueError(f"Unknown series '{series}'. Valid: {sorted(RATE_SERIES)}")

    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    result = (
        supabase.table("interest_rates")
        .select("date, value")
        .eq("series", series)
        .gte("date", cutoff)
        .order("date")
        .execute()
    )
    return result.data
