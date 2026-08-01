"""Big Picture perspective (Top-Down Analysis, layer 1 of 3).

Four sub-analyses, each backed by a real free source:
  1. Macro market analysis   -> CPI YoY trend classifies inflationary /
                                 disinflationary / deflationary (FRED CPIAUCSL)
  2. Interest rate analysis  -> higher / lower / unexpected-change / steady,
                                 extending the same 2Y-vs-funds-rate logic
                                 used elsewhere, plus a check for a recent
                                 discrete rate move that contradicts what
                                 was priced in beforehand
  3. Inter-market analysis   -> a broad commodity index (IMF's Global Price
                                 Index of All Commodities via FRED — the
                                 same kind of free official proxy DXY
                                 already uses for the dollar) plus USDX,
                                 reusing the DXY engine's own trend read
  4. Seasonal influences     -> monthly average return + win rate computed
                                 directly from our own stored price history
                                 (market_prices) — real historical
                                 tendencies, not a lookup table
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.cache import ttl_cache
from app.database import get_supabase
from app.services.market_data_service import ASSET_SYMBOLS, get_stored_bars
from app.services.treasury_service import _fetch_fred_series

CPI_SERIES_ID = "CPIAUCSL"
COMMODITY_SERIES_ID = "PALLFNFINDEXM"

RATE_JUMP_THRESHOLD_PP = 0.05     # day-over-day funds-rate change big enough to call a "move"
RATE_EXPECTATION_THRESHOLD_PP = 0.25
COMMODITY_TREND_THRESHOLD_PCT = 2.0  # % change over ~3 months before calling it a trend


# ---------------------------------------------------------------------------
# Refresh: pull raw series
# ---------------------------------------------------------------------------
async def refresh_cpi_data(days_back: int = 900) -> dict:
    supabase = get_supabase()
    observations = await _fetch_fred_series(CPI_SERIES_ID, days_back=days_back)
    rows = [{"date": o["date"], "value": o["value"]} for o in observations]
    if rows:
        supabase.table("cpi_data").upsert(rows, on_conflict="date").execute()
    return {"rows_upserted": len(rows)}


async def refresh_commodity_index(days_back: int = 900) -> dict:
    supabase = get_supabase()
    observations = await _fetch_fred_series(COMMODITY_SERIES_ID, days_back=days_back)
    rows = [{"date": o["date"], "value": o["value"], "source": "FRED_" + COMMODITY_SERIES_ID} for o in observations]
    if rows:
        supabase.table("commodity_index").upsert(rows, on_conflict="date").execute()
    return {"rows_upserted": len(rows)}


# ---------------------------------------------------------------------------
# Macro regime classification
# ---------------------------------------------------------------------------
def _cpi_yoy_series(cpi_rows: list[dict]) -> list[dict]:
    """[{date, yoy_pct}] — needs >=13 months of level data per point."""
    by_date = {r["date"]: r["value"] for r in cpi_rows}
    dates_sorted = sorted(by_date)
    yoy = []
    for i, date in enumerate(dates_sorted):
        target = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m")
        prior = next((by_date[d] for d in dates_sorted[:i] if d.startswith(target)), None)
        if prior:
            yoy.append({"date": date, "yoy_pct": (by_date[date] / prior - 1) * 100})
    return yoy


def _classify_inflation_regime(yoy_series: list[dict]) -> tuple[str | None, float | None]:
    if len(yoy_series) < 4:
        return None, None
    latest = yoy_series[-1]["yoy_pct"]
    three_months_ago = yoy_series[-4]["yoy_pct"]
    if latest < 0:
        return "deflationary", latest
    if latest > three_months_ago:
        return "inflationary", latest
    return "disinflationary", latest


async def _classify_rate_regime(supabase) -> str | None:
    rates_result = (
        supabase.table("interest_rates")
        .select("date, value")
        .eq("series", "FEDFUNDS")
        .order("date", desc=True)
        .limit(15)
        .execute()
    )
    rows = sorted(rates_result.data, key=lambda r: r["date"])  # ascending
    if len(rows) < 2:
        return None

    # Look for a discrete recent jump (an actual Fed move), not just drift.
    jump = None
    for prev, curr in zip(rows, rows[1:]):
        delta = curr["value"] - prev["value"]
        if abs(delta) >= RATE_JUMP_THRESHOLD_PP:
            jump = {"date": curr["date"], "delta": delta}

    two_year_result = (
        supabase.table("treasury_yields").select("date, value").eq("series", "2Y")
        .order("date", desc=True).limit(1).execute()
    )
    two_year_yield = two_year_result.data[0]["value"] if two_year_result.data else None
    funds_rate = rows[-1]["value"]

    if jump and two_year_yield is not None:
        expectation_sign = 1 if two_year_yield > funds_rate else -1
        move_sign = 1 if jump["delta"] > 0 else -1
        if expectation_sign != move_sign:
            return "unexpected_change"

    if two_year_yield is None:
        return None
    diff = two_year_yield - funds_rate
    if diff >= RATE_EXPECTATION_THRESHOLD_PP:
        return "higher_rates_expected"
    if diff <= -RATE_EXPECTATION_THRESHOLD_PP:
        return "lower_rates_expected"
    return "steady"


async def _commodity_trend(supabase) -> str | None:
    result = supabase.table("commodity_index").select("date, value").order("date", desc=True).limit(4).execute()
    if len(result.data) < 4:
        return None
    latest, three_back = result.data[0]["value"], result.data[3]["value"]
    change_pct = (latest / three_back - 1) * 100
    if change_pct > COMMODITY_TREND_THRESHOLD_PCT:
        return "up"
    if change_pct < -COMMODITY_TREND_THRESHOLD_PCT:
        return "down"
    return "flat"


async def _usdx_trend(supabase) -> str | None:
    result = supabase.table("dxy_forecasts").select("trend").order("created_at", desc=True).limit(1).execute()
    return result.data[0]["trend"] if result.data else None


async def compute_macro_regime() -> dict:
    supabase = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cpi_result = supabase.table("cpi_data").select("date, value").order("date", desc=True).limit(24).execute()
    inflation_regime, cpi_yoy = _classify_inflation_regime(_cpi_yoy_series(cpi_result.data))

    regime = {
        "as_of": today,
        "inflation_regime": inflation_regime,
        "cpi_yoy_pct": round(cpi_yoy, 2) if cpi_yoy is not None else None,
        "rate_regime": await _classify_rate_regime(supabase),
        "commodity_trend": await _commodity_trend(supabase),
        "usdx_trend": await _usdx_trend(supabase),
    }
    supabase.table("macro_regime").upsert(regime, on_conflict="as_of").execute()
    return regime


# ---------------------------------------------------------------------------
# Seasonality
# ---------------------------------------------------------------------------
async def refresh_seasonality() -> dict:
    supabase = get_supabase()
    rows_written = 0

    for asset in ASSET_SYMBOLS:
        bars = await get_stored_bars(asset)  # full available history
        if len(bars) < 30:
            continue

        by_month: dict[int, list[float]] = defaultdict(list)
        for prev_bar, bar in zip(bars, bars[1:]):
            month = int(bar["datetime"][5:7])
            daily_return_pct = (bar["close"] / prev_bar["close"] - 1) * 100
            by_month[month].append(daily_return_pct)

        years_by_month: dict[int, set[str]] = defaultdict(set)
        for bar in bars:
            years_by_month[int(bar["datetime"][5:7])].add(bar["datetime"][:4])

        for month, returns in by_month.items():
            avg_return = sum(returns) / len(returns)
            win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            supabase.table("seasonality_stats").upsert(
                {
                    "asset": asset,
                    "month": month,
                    "avg_return_pct": round(avg_return, 3),
                    "win_rate_pct": round(win_rate, 1),
                    "years_sampled": len(years_by_month[month]),
                },
                on_conflict="asset,month",
            ).execute()
            rows_written += 1

    return {"rows_written": rows_written}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
@ttl_cache(seconds=1800)
async def get_big_picture_summary(asset: str) -> dict:
    supabase = get_supabase()

    regime_result = supabase.table("macro_regime").select("*").order("as_of", desc=True).limit(1).execute()
    regime = regime_result.data[0] if regime_result.data else None

    seasonality_result = (
        supabase.table("seasonality_stats").select("*").eq("asset", asset).order("month").execute()
    )
    current_month = datetime.now(timezone.utc).month
    current_month_stats = next((s for s in seasonality_result.data if s["month"] == current_month), None)

    return {
        "asset": asset,
        "macro_regime": regime,
        "current_month_seasonality": current_month_stats,
        "seasonality_by_month": seasonality_result.data,
    }
