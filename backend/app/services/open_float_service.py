"""Macro Analysis — Quarterly Shift & Open Float.

Open Float, per this project's working definition: the study of how price
reaches for buy-side or sell-side liquidity resting above recent highs or
below recent lows. This module identifies where that liquidity currently
sits, how far away it is, and whether it's already been swept — using the
same swing/market-structure-shift detectors ICT (and the Intermediate
top-down perspective) already use, not a second structure engine. See
intermediate_service.py for the established resample -> detect_swings ->
detect_market_structure_shifts pattern this mirrors, just resampled to
'1Q' instead of '1W'/'1M'.

All levels are computed fresh from stored daily bars on every call — no
liquidity level is ever hard-coded, and there's nothing to migrate or
persist: a "swept" level is simply one where later price history broke
past it, which stored bars already answer without a dedicated table.
"""
from datetime import datetime, timedelta, timezone

from app.services.ict_service import SWING_WINDOW, detect_market_structure_shifts, detect_swings
from app.services.market_data_service import get_stored_bars, resample_bars

# Structural-logic parameters, named and centralized (not buried in
# function bodies) so they can be tuned later without hunting through logic.
SHIFT_LOOKBACK = 8  # quarterly candles considered for the shift detector
SWING_HIGH_LOOKBACK = 90  # days, short-term swing-high window
SWING_LOW_LOOKBACK = 90  # days, short-term swing-low window
MINIMUM_SHIFT_DISTANCE = 3  # bars between swings for detect_swings' own fractal window (see ict_service.SWING_WINDOW)
MAX_SHORT_TERM_LEVELS = 3  # cap on how many short-term swing highs/lows to surface

NEAR_PCT = 1.0
MODERATE_PCT = 3.0
# beyond MODERATE_PCT is classified FAR

# Importance weights per source — used for the dominant-side score, which
# section 7 of the spec requires NOT be distance-only. Higher timeframe
# liquidity outweighs a nearby but minor short-term swing.
IMPORTANCE_WEIGHTS = {"12M": 4, "6M": 3, "3M": 2, "short_term": 1, "shift": 2}


def _distance(current_price: float, level: float) -> dict:
    distance = level - current_price
    pct = (distance / current_price) * 100 if current_price else 0.0
    return {"distance": round(distance, 5), "pct_distance": round(pct, 3)}


def _proximity(pct_distance: float) -> str:
    abs_pct = abs(pct_distance)
    if abs_pct <= NEAR_PCT:
        return "NEAR"
    if abs_pct <= MODERATE_PCT:
        return "MODERATE"
    return "FAR"


def _bar_date(bar: dict) -> datetime:
    return datetime.strptime(bar["datetime"][:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _period_extreme(bars: list[dict], days: int) -> dict | None:
    """Highest high / lowest low within the last `days` *calendar* days —
    using real timestamps rather than a candle count, so a "3-month high"
    means the actual last three calendar months even across data gaps,
    per the spec's timeframe-correctness requirement."""
    if not bars:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    window = [b for b in bars if _bar_date(b) >= cutoff]
    if not window:
        return None
    high_bar = max(window, key=lambda b: b["high"])
    low_bar = min(window, key=lambda b: b["low"])
    return {
        "high": high_bar["high"],
        "high_date": high_bar["datetime"],
        "low": low_bar["low"],
        "low_date": low_bar["datetime"],
    }


def _sweep_status(bars: list[dict], level: float, level_date: str, side: str) -> str:
    """UNTOUCHED if price hasn't gone beyond this level since it was set;
    SWEPT if later price history broke past it. Only ever computed from
    real bars — never guessed, and a level is never deleted once swept,
    just labeled (see get_open_float_analysis's untouched-only filtering
    for "currently actionable" levels vs. the full history)."""
    after = [b for b in bars if b["datetime"] > level_date]
    if not after:
        return "UNTOUCHED"
    if side == "buy":
        return "SWEPT" if any(b["high"] > level for b in after) else "UNTOUCHED"
    return "SWEPT" if any(b["low"] < level for b in after) else "UNTOUCHED"


FALLBACK_QUARTER_LOOKBACK = 2  # quarters compared for a simple trend read when no confirmed shift exists yet


def _quarterly_shift(daily_bars: list[dict]) -> dict:
    """Mirrors intermediate_service.py's _bias_from_bars: prefer a
    confirmed structure shift, but fall back to a simple recent-trend
    comparison when there isn't enough quarterly history yet for one —
    expected for a while given how few real calendar quarters exist this
    early, and the same accepted limitation the app's monthly/weekly bias
    already has."""
    quarterly_bars = resample_bars(daily_bars, "1Q")
    recent = quarterly_bars[-SHIFT_LOOKBACK:]

    if len(recent) < 3:
        current = quarterly_bars[-1] if quarterly_bars else None
        return {
            "direction": "neutral",
            "notes": "Not enough quarterly history yet for a confirmed shift",
            "last_bullish_shift": None,
            "last_bearish_shift": None,
            "current_quarter_high": current["high"] if current else None,
            "current_quarter_low": current["low"] if current else None,
        }

    window = min(SWING_WINDOW, (len(recent) - 1) // 2) or 1
    swings = detect_swings(recent, window=window)
    shifts = detect_market_structure_shifts(recent, swings)

    last_bullish = next((s for s in reversed(shifts) if s["direction"] == "bullish"), None)
    last_bearish = next((s for s in reversed(shifts) if s["direction"] == "bearish"), None)
    current_quarter = quarterly_bars[-1]

    if shifts:
        direction = shifts[-1]["direction"]
        notes = shifts[-1]["notes"]
    else:
        lookback = recent[-FALLBACK_QUARTER_LOOKBACK - 1 :]
        change_pct = (lookback[-1]["close"] / lookback[0]["close"] - 1) * 100
        if change_pct > 1:
            direction, notes = "bullish", f"No confirmed structure shift yet; {change_pct:.1f}% over last {len(lookback)} quarters"
        elif change_pct < -1:
            direction, notes = "bearish", f"No confirmed structure shift yet; {change_pct:.1f}% over last {len(lookback)} quarters"
        else:
            direction, notes = "neutral", f"No confirmed structure shift yet; roughly flat over last {len(lookback)} quarters"

    return {
        "direction": direction,
        "notes": notes,
        "last_bullish_shift": last_bullish,
        "last_bearish_shift": last_bearish,
        "current_quarter_high": current_quarter["high"],
        "current_quarter_low": current_quarter["low"],
    }


def _short_term_levels(daily_bars: list[dict], current_price: float) -> tuple[list[dict], list[dict]]:
    """Recent, meaningful swing highs/lows only — not every minor candle
    extreme. Filtered to the swing-lookback window, capped at
    MAX_SHORT_TERM_LEVELS, most recent first."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(SWING_HIGH_LOOKBACK, SWING_LOW_LOOKBACK))
    recent_bars = [b for b in daily_bars if _bar_date(b) >= cutoff]
    if len(recent_bars) < SWING_WINDOW * 2 + 1:
        return [], []

    swings = detect_swings(recent_bars, window=SWING_WINDOW)
    highs = sorted((s for s in swings if s["type"] == "swing_high"), key=lambda s: s["datetime"], reverse=True)
    lows = sorted((s for s in swings if s["type"] == "swing_low"), key=lambda s: s["datetime"], reverse=True)

    def _shape(level: dict, side: str) -> dict:
        d = _distance(current_price, level["price"])
        return {
            "price": level["price"],
            "date": level["datetime"],
            **d,
            "importance": "high" if abs(d["pct_distance"]) <= NEAR_PCT else "moderate",
            "sweep_status": _sweep_status(daily_bars, level["price"], level["datetime"], side),
        }

    return (
        [_shape(h, "buy") for h in highs[:MAX_SHORT_TERM_LEVELS]],
        [_shape(l, "sell") for l in lows[:MAX_SHORT_TERM_LEVELS]],
    )


def _period_level(daily_bars: list[dict], current_price: float, days: int, label: str, side: str) -> dict | None:
    extreme = _period_extreme(daily_bars, days)
    if extreme is None:
        return None
    price = extreme["high"] if side == "buy" else extreme["low"]
    date = extreme["high_date"] if side == "buy" else extreme["low_date"]
    d = _distance(current_price, price)
    return {
        "label": label,
        "price": price,
        "date": date,
        **d,
        "liquidity_status": _proximity(d["pct_distance"]),
        "sweep_status": _sweep_status(daily_bars, price, date, side),
    }


def _dominant_side(buy_levels: list[dict], sell_levels: list[dict], quarterly_direction: str) -> dict:
    """Per spec section 7: not distance alone. Scores each side by summed
    importance weight of its still-UNTOUCHED levels, then nudges the score
    slightly toward the side price is more likely to reach given the
    current quarterly bias (a bearish quarter favors price eventually
    reaching down into sell-side liquidity, and vice versa)."""

    def score(levels: list[dict]) -> float:
        total = 0.0
        for lvl in levels:
            if lvl.get("sweep_status") == "SWEPT":
                continue
            total += IMPORTANCE_WEIGHTS.get(lvl.get("_source", "short_term"), 1)
        return total

    buy_score = score(buy_levels)
    sell_score = score(sell_levels)

    if quarterly_direction == "bearish":
        sell_score *= 1.15
    elif quarterly_direction == "bullish":
        buy_score *= 1.15

    if abs(buy_score - sell_score) < 0.5:
        side = "BALANCED"
    else:
        side = "BUY_SIDE" if buy_score > sell_score else "SELL_SIDE"

    return {"dominant_liquidity_side": side, "buy_side_score": round(buy_score, 2), "sell_side_score": round(sell_score, 2)}


def _nearest(levels: list[dict]) -> dict | None:
    untouched = [lvl for lvl in levels if lvl.get("sweep_status") != "SWEPT"]
    pool = untouched or levels
    if not pool:
        return None
    return min(pool, key=lambda lvl: abs(lvl["pct_distance"]))


def _interpretation(quarterly: dict, dominance: dict, nearest_buy: dict | None, nearest_sell: dict | None) -> str:
    """A plain-language read built directly from the calculated fields
    below it — not a separate LLM call. Keeps this section honest to the
    spec's "based strictly on the calculated data" requirement and avoids
    spending API calls on every page load just to restate numbers already
    on screen."""
    parts = [f"Quarterly bias is {quarterly['direction']} ({quarterly['price_position']})."]

    if nearest_sell:
        parts.append(
            f"Nearest sell-side liquidity is {nearest_sell.get('label', 'a short-term low')} at "
            f"{nearest_sell['price']} ({nearest_sell['pct_distance']:+.2f}%, {nearest_sell['sweep_status'].lower()})."
        )
    if nearest_buy:
        parts.append(
            f"Nearest buy-side liquidity is {nearest_buy.get('label', 'a short-term high')} at "
            f"{nearest_buy['price']} ({nearest_buy['pct_distance']:+.2f}%, {nearest_buy['sweep_status'].lower()})."
        )

    side = dominance["dominant_liquidity_side"]
    if side == "BALANCED":
        parts.append("Open float is roughly balanced between buy-side and sell-side liquidity right now.")
    else:
        parts.append(f"Dominant open float currently favors the {side.replace('_', '-').lower()}.")

    return " ".join(parts)


async def get_open_float_analysis(asset: str) -> dict:
    """The full Quarterly Shift & Open Float read for one asset. Returns
    "Data unavailable" markers rather than guessed values wherever stored
    history doesn't cover a requested window — never a fabricated level."""
    daily_bars = await get_stored_bars(asset, days_back=400)  # covers 12M + swing lookback with margin

    if not daily_bars:
        return {"asset": asset, "error": "Data unavailable — no stored price history for this asset yet"}

    current_price = daily_bars[-1]["close"]
    quarterly = _quarterly_shift(daily_bars)

    short_term_highs, short_term_lows = _short_term_levels(daily_bars, current_price)
    for lvl in short_term_highs + short_term_lows:
        lvl["_source"] = "short_term"

    three_month = _period_level(daily_bars, current_price, 90, "3M High", "buy")
    six_month = _period_level(daily_bars, current_price, 182, "6M High", "buy")
    twelve_month = _period_level(daily_bars, current_price, 365, "12M High", "buy")
    for lvl, source in ((three_month, "3M"), (six_month, "6M"), (twelve_month, "12M")):
        if lvl:
            lvl["_source"] = source

    three_month_low = _period_level(daily_bars, current_price, 90, "3M Low", "sell")
    six_month_low = _period_level(daily_bars, current_price, 182, "6M Low", "sell")
    twelve_month_low = _period_level(daily_bars, current_price, 365, "12M Low", "sell")
    for lvl, source in ((three_month_low, "3M"), (six_month_low, "6M"), (twelve_month_low, "12M")):
        if lvl:
            lvl["_source"] = source

    last_bearish = quarterly["last_bearish_shift"]
    bearish_shift_level = None
    if last_bearish:
        d = _distance(current_price, last_bearish["price"])
        bearish_shift_level = {
            "label": "Last Bearish Shift",
            "price": last_bearish["price"],
            "date": last_bearish["datetime"],
            **d,
            "sweep_status": _sweep_status(daily_bars, last_bearish["price"], last_bearish["datetime"], "buy"),
            "_source": "shift",
        }

    last_bullish = quarterly["last_bullish_shift"]
    bullish_shift_level = None
    if last_bullish:
        d = _distance(current_price, last_bullish["price"])
        bullish_shift_level = {
            "label": "Last Bullish Shift",
            "price": last_bullish["price"],
            "date": last_bullish["datetime"],
            **d,
            "sweep_status": _sweep_status(daily_bars, last_bullish["price"], last_bullish["datetime"], "sell"),
            "_source": "shift",
        }

    buy_side_levels = [lvl for lvl in [bearish_shift_level, *short_term_highs, three_month, six_month, twelve_month] if lvl]
    sell_side_levels = [lvl for lvl in [bullish_shift_level, *short_term_lows, three_month_low, six_month_low, twelve_month_low] if lvl]

    dominance = _dominant_side(buy_side_levels, sell_side_levels, quarterly["direction"])

    quarter_high, quarter_low = quarterly["current_quarter_high"], quarterly["current_quarter_low"]
    if quarter_high is not None and quarter_low is not None:
        if current_price > quarter_high:
            quarter_position = "above quarterly range"
        elif current_price < quarter_low:
            quarter_position = "below quarterly range"
        else:
            quarter_position = "inside quarterly range"
    else:
        quarter_position = "Data unavailable"

    def _strip_internal(lvl: dict) -> dict:
        return {k: v for k, v in lvl.items() if not k.startswith("_")}

    nearest_buy = _nearest(buy_side_levels)
    nearest_sell = _nearest(sell_side_levels)
    nearest_buy_clean = _strip_internal(nearest_buy) if nearest_buy else None
    nearest_sell_clean = _strip_internal(nearest_sell) if nearest_sell else None

    quarterly_shift_response = {
        "direction": quarterly["direction"],
        "notes": quarterly["notes"],
        "current_quarter_high": quarter_high,
        "current_quarter_low": quarter_low,
        "price_position": quarter_position,
    }

    return {
        "asset": asset,
        "current_price": current_price,
        "as_of": daily_bars[-1]["datetime"],
        "quarterly_shift": quarterly_shift_response,
        "buy_side": {
            "last_bearish_shift": _strip_internal(bearish_shift_level) if bearish_shift_level else "Data unavailable",
            "short_term_highs": [_strip_internal(lvl) for lvl in short_term_highs],
            "three_month_high": _strip_internal(three_month) if three_month else "Data unavailable",
            "six_month_high": _strip_internal(six_month) if six_month else "Data unavailable",
            "twelve_month_high": _strip_internal(twelve_month) if twelve_month else "Data unavailable",
        },
        "sell_side": {
            "last_bullish_shift": _strip_internal(bullish_shift_level) if bullish_shift_level else "Data unavailable",
            "short_term_lows": [_strip_internal(lvl) for lvl in short_term_lows],
            "three_month_low": _strip_internal(three_month_low) if three_month_low else "Data unavailable",
            "six_month_low": _strip_internal(six_month_low) if six_month_low else "Data unavailable",
            "twelve_month_low": _strip_internal(twelve_month_low) if twelve_month_low else "Data unavailable",
        },
        "nearest_buy_side": nearest_buy_clean,
        "nearest_sell_side": nearest_sell_clean,
        **dominance,
        "interpretation": _interpretation(quarterly_shift_response, dominance, nearest_buy_clean, nearest_sell_clean),
    }
