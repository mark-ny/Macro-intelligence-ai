"""Short-Term perspective (Top-Down Analysis, layer 3 of 3).

Three sub-analyses:
  1. Correlation analysis -> Pearson correlation of daily % returns across
                              Gold, Nasdaq(QQQ), USDX, and the 10Y Treasury
                              yield — real numbers from our own stored
                              data, not a textbook assumption about "gold
                              vs dollar" being reasserted every refresh.
  2. Time and price theory -> previous day/week/month high-low reference
                              levels (the "price" component — fully real
                              with daily bars) plus a day-of-week return
                              tendency (the closest honest "time" component
                              we can compute without intraday data — true
                              ICT kill-zone timing needs hourly bars, which
                              is a paid tier; see ICT engine's own scope note).
  3. IPDA                  -> the Interbank Price Delivery Algorithm concept
                              operationalized as rolling 20/40/60-day
                              high-low ranges, with today's close classified
                              against each range — the standard practical
                              definition traders use for "IPDA ranges."
"""
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from app.cache import ttl_cache
from app.database import get_supabase
from app.services.market_data_service import ASSET_SYMBOLS, get_stored_bars, resample_bars

CORRELATION_SERIES = ("XAUUSD", "NQ", "USDX", "US10Y")
CORRELATION_WINDOW_DAYS = 60
IPDA_RANGE_SIZES = (20, 40, 60)
RANGE_EDGE_TOLERANCE = 0.001  # within 0.1% of the range edge counts as "at" rather than "inside"


# ---------------------------------------------------------------------------
# Correlation analysis
# ---------------------------------------------------------------------------
async def _series_returns(supabase, name: str) -> dict[str, float]:
    """{date: pct_return}, close-to-close, for whichever series `name` maps to."""
    if name in ("XAUUSD", "NQ"):
        bars = await get_stored_bars(name, days_back=CORRELATION_WINDOW_DAYS * 3)
        points = [(b["datetime"][:10], b["close"]) for b in bars]
    elif name == "USDX":
        result = supabase.table("dxy_data").select("date, value").order("date", desc=True).limit(200).execute()
        points = sorted((r["date"], r["value"]) for r in result.data)
    elif name == "US10Y":
        result = (
            supabase.table("treasury_yields").select("date, value").eq("series", "10Y")
            .order("date", desc=True).limit(200).execute()
        )
        points = sorted((r["date"], r["value"]) for r in result.data)
    else:
        raise ValueError(f"Unknown correlation series '{name}'")

    returns = {}
    for (prev_date, prev_value), (date, value) in zip(points, points[1:]):
        if prev_value:
            returns[date] = (value / prev_value - 1) * 100
    return returns


async def compute_correlations(window_days: int = CORRELATION_WINDOW_DAYS) -> dict:
    supabase = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    returns_by_series = {name: await _series_returns(supabase, name) for name in CORRELATION_SERIES}

    rows_written = 0
    for i, asset_a in enumerate(CORRELATION_SERIES):
        for asset_b in CORRELATION_SERIES[i + 1 :]:
            common_dates = sorted(set(returns_by_series[asset_a]) & set(returns_by_series[asset_b]))
            common_dates = common_dates[-window_days:]
            if len(common_dates) < 10:
                continue

            x = np.array([returns_by_series[asset_a][d] for d in common_dates])
            y = np.array([returns_by_series[asset_b][d] for d in common_dates])
            correlation = float(np.corrcoef(x, y)[0, 1])

            supabase.table("correlation_matrix").upsert(
                {
                    "as_of": today, "asset_a": asset_a, "asset_b": asset_b,
                    "correlation": round(correlation, 3), "window_days": len(common_dates),
                },
                on_conflict="as_of,asset_a,asset_b,window_days",
            ).execute()
            rows_written += 1

    return {"rows_written": rows_written}


@ttl_cache(seconds=1800)
async def get_correlations() -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("correlation_matrix").select("*")
        .order("as_of", desc=True).limit(len(CORRELATION_SERIES) ** 2).execute()
    )
    seen_pairs = set()
    latest = []
    for row in result.data:
        pair = (row["asset_a"], row["asset_b"], row["window_days"])
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            latest.append(row)
    return latest


# ---------------------------------------------------------------------------
# Time and price theory
# ---------------------------------------------------------------------------
@ttl_cache(seconds=1800)
async def get_time_price_levels(asset: str) -> dict:
    daily_bars = await get_stored_bars(asset)
    if len(daily_bars) < 30:
        return {"asset": asset, "price_levels": None, "day_of_week_tendency": None}

    weekly_bars = resample_bars(daily_bars, "1W")
    monthly_bars = resample_bars(daily_bars, "1M")

    price_levels = {
        "previous_day": {"high": daily_bars[-2]["high"], "low": daily_bars[-2]["low"]},
        "previous_week": {"high": weekly_bars[-2]["high"], "low": weekly_bars[-2]["low"]} if len(weekly_bars) >= 2 else None,
        "previous_month": {"high": monthly_bars[-2]["high"], "low": monthly_bars[-2]["low"]} if len(monthly_bars) >= 2 else None,
    }

    returns_by_weekday: dict[int, list[float]] = defaultdict(list)
    for prev_bar, bar in zip(daily_bars, daily_bars[1:]):
        weekday = datetime.strptime(bar["datetime"][:10], "%Y-%m-%d").weekday()  # 0=Mon
        returns_by_weekday[weekday].append((bar["close"] / prev_bar["close"] - 1) * 100)

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    tendency = [
        {"day": weekday_names[wd], "avg_return_pct": round(sum(rs) / len(rs), 3), "samples": len(rs)}
        for wd, rs in sorted(returns_by_weekday.items())
        if wd < 5  # markets are closed weekends; any stray weekend bar isn't meaningful
    ]

    return {"asset": asset, "price_levels": price_levels, "day_of_week_tendency": tendency}


# ---------------------------------------------------------------------------
# IPDA ranges
# ---------------------------------------------------------------------------
def _classify_position(close: float, range_high: float, range_low: float) -> str:
    if close > range_high:
        return "beyond_high"
    if close < range_low:
        return "beyond_low"
    if close >= range_high * (1 - RANGE_EDGE_TOLERANCE):
        return "at_high"
    if close <= range_low * (1 + RANGE_EDGE_TOLERANCE):
        return "at_low"
    return "inside"


async def refresh_ipda_ranges() -> dict:
    supabase = get_supabase()
    rows_written = 0

    for asset in ASSET_SYMBOLS:
        bars = await get_stored_bars(asset)
        if len(bars) < max(IPDA_RANGE_SIZES) + 1:
            continue

        current = bars[-1]
        for range_days in IPDA_RANGE_SIZES:
            window = bars[-(range_days + 1) : -1]  # the N bars *before* today, so today can be "beyond" them
            range_high = max(b["high"] for b in window)
            range_low = min(b["low"] for b in window)

            supabase.table("ipda_ranges").upsert(
                {
                    "asset": asset, "range_days": range_days,
                    "range_high": range_high, "range_low": range_low,
                    "current_close": current["close"],
                    "position": _classify_position(current["close"], range_high, range_low),
                    "as_of": current["datetime"][:10],
                },
                on_conflict="asset,range_days,as_of",
            ).execute()
            rows_written += 1

    return {"rows_written": rows_written}


@ttl_cache(seconds=1800)
async def get_ipda_ranges(asset: str) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("ipda_ranges").select("*").eq("asset", asset)
        .order("as_of", desc=True).limit(len(IPDA_RANGE_SIZES)).execute()
    )
    return result.data


@ttl_cache(seconds=1800)
async def get_short_term_summary(asset: str) -> dict:
    return {
        "asset": asset,
        "correlations": await get_correlations(),
        "time_and_price": await get_time_price_levels(asset),
        "ipda_ranges": await get_ipda_ranges(asset),
    }
