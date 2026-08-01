"""Intermediate perspective (Top-Down Analysis, layer 2 of 3).

Three sub-analyses:
  1. Top-down analysis  -> resamples our own stored daily bars into weekly
                            and monthly OHLC, then reruns the exact same
                            swing/market-structure-shift detectors ICT uses
                            on daily bars — same method, three lenses.
  2. COT data           -> CFTC's Commitment of Traders report (Legacy
                            Futures Only), fetched from their public Socrata
                            API. No key needed, though an unauthenticated IP
                            can be rate-limited under sustained heavy use —
                            fine for one weekly-ish pull per asset.
  3. Market sentiment   -> combines the News engine's headline sentiment
                            with COT positioning (extreme net-speculator
                            positioning is a classic sentiment gauge) into
                            one read, rather than treating "sentiment" as a
                            single opaque number.
"""
from datetime import datetime, timezone

import httpx

from app.cache import ttl_cache
from app.database import get_supabase
from app.services.ict_service import detect_market_structure_shifts, detect_swings
from app.services.market_data_service import ASSET_SYMBOLS, get_stored_bars, resample_bars

COT_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# SoQL LIKE patterns matched against market_and_exchange_names — a
# contains-match is more robust than an exact string, since the CFTC's
# exact naming/punctuation for a contract can vary by report vintage.
COT_MARKET_PATTERNS: dict[str, str] = {
    "XAUUSD": "%GOLD%COMMODITY EXCHANGE%",
    "NQ": "%NASDAQ-100%",
}

TOP_DOWN_TIMEFRAMES = ("1M", "1W", "1D")
FALLBACK_TREND_LOOKBACK = 10  # bars, used only when no structure shift is available yet


# ---------------------------------------------------------------------------
# Top-down multi-timeframe bias
# ---------------------------------------------------------------------------
def _bias_from_bars(bars: list[dict]) -> tuple[str, str]:
    """Returns (bias, notes). Prefers the most recent market structure
    shift; falls back to a simple recent-trend comparison when there
    isn't enough resampled history yet for a confirmed shift (common for
    '1M' early on, since it takes years of daily bars to accumulate many
    monthly candles)."""
    if len(bars) < 7:
        return "neutral", "Not enough history yet for this timeframe"

    swings = detect_swings(bars, window=min(3, (len(bars) - 1) // 2))
    shifts = detect_market_structure_shifts(bars, swings)
    if shifts:
        last = shifts[-1]
        return last["direction"], last["notes"]

    lookback = bars[-FALLBACK_TREND_LOOKBACK:] if len(bars) > FALLBACK_TREND_LOOKBACK else bars
    change_pct = (lookback[-1]["close"] / lookback[0]["close"] - 1) * 100
    if change_pct > 1:
        return "bullish", f"No confirmed structure shift yet; {change_pct:.1f}% over last {len(lookback)} bars"
    if change_pct < -1:
        return "bearish", f"No confirmed structure shift yet; {change_pct:.1f}% over last {len(lookback)} bars"
    return "neutral", f"No confirmed structure shift yet; roughly flat over last {len(lookback)} bars"


async def refresh_topdown_bias() -> dict:
    supabase = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows_written = 0

    for asset in ASSET_SYMBOLS:
        daily_bars = await get_stored_bars(asset)
        if not daily_bars:
            continue

        for timeframe in TOP_DOWN_TIMEFRAMES:
            tf_bars = resample_bars(daily_bars, timeframe)
            bias, notes = _bias_from_bars(tf_bars)
            supabase.table("topdown_bias").upsert(
                {"asset": asset, "timeframe": timeframe, "bias": bias, "as_of": today, "notes": notes},
                on_conflict="asset,timeframe,as_of",
            ).execute()
            rows_written += 1

    return {"rows_written": rows_written}


# ---------------------------------------------------------------------------
# COT positioning
# ---------------------------------------------------------------------------
async def refresh_cot_data(reports_back: int = 26) -> dict:
    rows_written = 0
    errors: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=20.0) as client:
        for asset, pattern in COT_MARKET_PATTERNS.items():
            try:
                response = await client.get(
                    COT_URL,
                    params={
                        "$where": f"upper(market_and_exchange_names) like '{pattern}'",
                        "$order": "report_date_as_yyyy_mm_dd DESC",
                        "$limit": reports_back,
                    },
                )
                response.raise_for_status()
                records = response.json()
            except Exception as exc:  # noqa: BLE001
                errors[asset] = str(exc)
                continue

            supabase = get_supabase()
            rows = []
            for r in records:
                try:
                    rows.append({
                        "report_date": r["report_date_as_yyyy_mm_dd"][:10],
                        "asset": asset,
                        "market_name": r.get("market_and_exchange_names"),
                        "noncommercial_long": int(float(r.get("noncomm_positions_long_all", 0))),
                        "noncommercial_short": int(float(r.get("noncomm_positions_short_all", 0))),
                        "commercial_long": int(float(r.get("comm_positions_long_all", 0))),
                        "commercial_short": int(float(r.get("comm_positions_short_all", 0))),
                    })
                except (KeyError, ValueError, TypeError):
                    continue  # skip a malformed row rather than failing the whole refresh

            if rows:
                supabase.table("cot_positioning").upsert(rows, on_conflict="report_date,asset").execute()
                rows_written += len(rows)

    return {"rows_written": rows_written, "assets_with_errors": errors}


# ---------------------------------------------------------------------------
# Market sentiment (news + COT combined)
# ---------------------------------------------------------------------------
@ttl_cache(seconds=1800)
async def get_market_sentiment(asset: str) -> dict:
    supabase = get_supabase()

    news_result = (
        supabase.table("economic_news").select("sentiment").in_("related_asset", [asset, "both"])
        .order("published_at", desc=True).limit(20).execute()
    )
    news_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for row in news_result.data:
        news_counts[row["sentiment"]] = news_counts.get(row["sentiment"], 0) + 1

    cot_result = (
        supabase.table("cot_positioning").select("*").eq("asset", asset)
        .order("report_date", desc=True).limit(1).execute()
    )
    cot_latest = cot_result.data[0] if cot_result.data else None
    cot_reading = None
    if cot_latest:
        net = cot_latest["noncommercial_long"] - cot_latest["noncommercial_short"]
        total = cot_latest["noncommercial_long"] + cot_latest["noncommercial_short"]
        net_pct = round(net / total * 100, 1) if total else None
        cot_reading = {
            "report_date": cot_latest["report_date"],
            "net_noncommercial": net,
            "net_noncommercial_pct": net_pct,
            "positioning": "net long" if net > 0 else "net short" if net < 0 else "flat",
        }

    return {"asset": asset, "news_sentiment_counts": news_counts, "cot_positioning": cot_reading}


@ttl_cache(seconds=1800)
async def get_intermediate_summary(asset: str) -> dict:
    supabase = get_supabase()

    bias_result = (
        supabase.table("topdown_bias").select("timeframe, bias, notes, as_of")
        .eq("asset", asset).order("as_of", desc=True).limit(len(TOP_DOWN_TIMEFRAMES)).execute()
    )
    bias_by_timeframe = {row["timeframe"]: row for row in bias_result.data}

    sentiment = await get_market_sentiment(asset)

    return {
        "asset": asset,
        "top_down_bias": {tf: bias_by_timeframe.get(tf) for tf in TOP_DOWN_TIMEFRAMES},
        "sentiment": sentiment,
    }
