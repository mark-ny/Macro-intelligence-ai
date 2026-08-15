"""IPDA Data Ranges — repaired and upgraded.

Audit summary: the existing short_term_service.refresh_ipda_ranges() /
get_ipda_ranges() was not broken — it already correctly uses trading-
session bar counts (not calendar-day approximations) for its 20/40/60-day
rolling ranges, and is already wired into the scheduler and the top-down
refresh endpoint. It was simply far short of the full IPDA framework: no
benchmark comparison, no smart-money accumulation/distribution patterns,
no institutional reference points, no cast-forward, no Open Float
connection. This module adds all of that as a new, more complete engine
on top of the same correct trading-day-window primitive, reusing
ict_service's swing/structure/order-block/FVG detectors and
open_float_service's distance/proximity helpers rather than duplicating
them. short_term_service's own IPDA functions are untouched — nothing
that already consumed them (the Short-Term top-down page) changes.
"""
import json
from datetime import datetime, timedelta, timezone

from app.database import get_supabase
from app.services.ict_service import (
    classify_market_structure,
    detect_fair_value_gaps,
    detect_market_structure_shifts,
    detect_order_blocks,
    detect_swings,
)
from app.services.market_data_service import ASSET_SYMBOLS, get_stored_bars
from app.services.open_float_service import _bar_date, _distance, _proximity

# Primary IPDA range: "3-4 months" of actual trading sessions, not
# calendar days. A trading year runs ~252 sessions, so one quarter is
# ~63 — using the upper end of the spec's stated range as one
# configurable window.
PRIMARY_RANGE_SESSIONS = 65

# The three trading-day windows the spec keys Quarterly Shift, Open
# Float, and Cast Forward off of throughout.
TRADING_DAY_WINDOWS = (20, 40, 60)

# Not hard-coded to one benchmark for every market — configurable here,
# reusing the same DXY/Treasury series short_term_service's correlation
# analysis already pulls from rather than adding a new data source.
BENCHMARK_MAP = {"XAUUSD": "USDX", "NQ": "US10Y"}

# ~5 trading sessions per calendar week -> used only to *estimate* a
# calendar date for Cast Forward windows, since there's no live trading
# calendar/holiday feed available; the trading-day count itself (the
# figure that actually matters) is always exact, never approximated.
CALENDAR_DAYS_PER_TRADING_DAY = 7 / 5

MITIGATION_LOOKAHEAD_MIN_BARS = 1


def _safe_json(value):
    return json.loads(json.dumps(value, default=str))


async def _benchmark_bars(benchmark_symbol: str, count: int) -> list[dict]:
    """Degenerate OHLC bars (high=low=close=value) for a single-value
    daily series like DXY or Treasury yields, so the same swing/structure
    detectors built for real OHLC bars can run on them unchanged — reusing
    the engine instead of writing a second one for single-value series.
    Real OHLC assets (XAUUSD/NQ) go through get_stored_bars normally."""
    if benchmark_symbol in ASSET_SYMBOLS:
        return await get_stored_bars(benchmark_symbol, days_back=int(count * 1.6))

    supabase = get_supabase()
    if benchmark_symbol == "USDX":
        result = supabase.table("dxy_data").select("date, value").order("date", desc=True).limit(count).execute()
    elif benchmark_symbol == "US10Y":
        result = (
            supabase.table("treasury_yields").select("date, value").eq("series", "10Y")
            .order("date", desc=True).limit(count).execute()
        )
    else:
        return []

    rows = sorted(result.data, key=lambda r: r["date"])
    return [
        {"datetime": r["date"], "open": r["value"], "high": r["value"], "low": r["value"], "close": r["value"]}
        for r in rows
        if r.get("value") is not None
    ]


def _label_swings(swings: list[dict]) -> list[dict]:
    """Classifies each swing as HH/LH (swing highs) or HL/LL (swing lows)
    relative to the immediately preceding swing of the same type."""
    labeled = []
    last_high = last_low = None
    for s in swings:
        entry = dict(s)
        if s["type"] == "swing_high":
            entry["label"] = "HH" if last_high is None or s["price"] > last_high else "LH"
            last_high = s["price"]
        else:
            entry["label"] = "LL" if last_low is None or s["price"] < last_low else "HL"
            last_low = s["price"]
        labeled.append(entry)
    return labeled


def _latest(swings: list[dict], swing_type: str) -> dict | None:
    matches = [s for s in swings if s["type"] == swing_type]
    return matches[-1] if matches else None


def _detect_manipulation(underlying_bars: list[dict], benchmark_bars: list[dict], lookback: int = 10) -> dict | None:
    """Simplified heuristic for Pattern A: the underlying breaks beyond
    its own recent range and reverses back inside within a few bars,
    without the benchmark making a comparably-sized move — a defensible
    proxy for "meaningful manipulation/divergence" given daily bars, not
    a strict definition. Clearly labeled as a heuristic in the response."""
    if len(underlying_bars) < lookback + 3 or len(benchmark_bars) < lookback + 3:
        return None

    recent = underlying_bars[-(lookback + 3) : -3]
    prior_high = max(b["high"] for b in recent)
    prior_low = min(b["low"] for b in recent)
    last_three = underlying_bars[-3:]

    broke_high = any(b["high"] > prior_high for b in last_three)
    broke_low = any(b["low"] < prior_low for b in last_three)
    closed_back_inside = prior_low <= last_three[-1]["close"] <= prior_high

    if not ((broke_high or broke_low) and closed_back_inside):
        return None

    bench_recent = benchmark_bars[-(lookback + 3) : -3]
    bench_range = max(b["high"] for b in bench_recent) - min(b["low"] for b in bench_recent)
    bench_last_three_range = max(b["high"] for b in benchmark_bars[-3:]) - min(b["low"] for b in benchmark_bars[-3:])
    benchmark_confirmed = bench_range > 0 and (bench_last_three_range / bench_range) > 0.5

    if benchmark_confirmed:
        return None  # benchmark moved comparably too -> not a divergence

    direction = "bullish" if broke_low else "bearish"  # swept sell-side liquidity then reversed up = bullish manipulation
    return {
        "pattern": "A — Manipulation",
        "direction": direction,
        "datetime": underlying_bars[-1]["datetime"],
        "notes": "Underlying broke its recent range and closed back inside without a comparable benchmark move",
        "status": "unconfirmed",
    }


def _smart_money_programs(underlying_swings: list[dict], benchmark_swings: list[dict]) -> dict:
    u_high, u_low = _latest(underlying_swings, "swing_high"), _latest(underlying_swings, "swing_low")
    b_high, b_low = _latest(benchmark_swings, "swing_high"), _latest(benchmark_swings, "swing_low")

    buy_patterns, sell_patterns = [], []

    def _record(patterns: list, label: str, name: str, u_ref: dict, b_ref: dict):
        patterns.append(
            {
                "pattern": label,
                "classification": name,
                "underlying_structure": {"label": u_ref["label"], "price": u_ref["price"], "datetime": u_ref["datetime"]},
                "benchmark_structure": {"label": b_ref["label"], "price": b_ref["price"], "datetime": b_ref["datetime"]},
                "status": "unconfirmed",
            }
        )

    # Buy Program
    if b_low and u_low and b_low["label"] == "LL" and u_low["label"] == "HL":
        _record(buy_patterns, "B", "BUY PROGRAM / ACCUMULATION", u_low, b_low)
    if u_low and b_high and u_low["label"] == "LL" and b_high["label"] == "LH":
        _record(buy_patterns, "C", "Potential accumulation / relative divergence", u_low, b_high)
    if b_high and u_low and b_high["label"] == "HH" and u_low["label"] == "HL":
        _record(buy_patterns, "D", "Potential accumulation condition", u_low, b_high)

    # Sell Program
    if b_high and u_high and b_high["label"] == "HH" and u_high["label"] == "LH":
        _record(sell_patterns, "B", "SELL PROGRAM / DISTRIBUTION", u_high, b_high)
    if u_high and b_low and u_high["label"] == "HH" and b_low["label"] == "HL":
        _record(sell_patterns, "C", "Potential distribution", u_high, b_low)
    if b_low and u_high and b_low["label"] == "LL" and u_high["label"] == "LH":
        _record(sell_patterns, "D", "Potential sell-program condition", u_high, b_low)

    return {"buy_program": buy_patterns, "sell_program": sell_patterns}


def _window_analysis(bars: list[dict], window: int) -> dict:
    """One trading-day window (20/40/60): high/low/open/close/range,
    structure, major swings, and the most recent shift within it — feeds
    both Quarterly Shift and, via the caller, Open Float. Falls back to a
    simple open-vs-close trend read when the window is too short/clean
    for a confirmed swing structure — same reasoning as
    open_float_service._quarterly_shift's fallback."""
    if len(bars) < window + 1:
        return {"status": "INSUFFICIENT DATA"}

    segment = bars[-window:]
    swings = detect_swings(segment, window=min(3, (window - 1) // 2) or 1)
    structure = classify_market_structure(swings)
    shifts = detect_market_structure_shifts(segment, swings)

    trend = structure.get("trend", "unknown")
    if trend in ("RANGE", "unknown") and not shifts:
        change_pct = (segment[-1]["close"] / segment[0]["open"] - 1) * 100
        if change_pct > 1:
            trend = "BULLISH (unconfirmed)"
        elif change_pct < -1:
            trend = "BEARISH (unconfirmed)"

    return {
        "trading_days": window,
        "high": max(b["high"] for b in segment),
        "low": min(b["low"] for b in segment),
        "open": segment[0]["open"],
        "close": segment[-1]["close"],
        "range": round(max(b["high"] for b in segment) - min(b["low"] for b in segment), 5),
        "structure": trend,
        "major_swing_highs": [s for s in swings if s["type"] == "swing_high"][-3:],
        "major_swing_lows": [s for s in swings if s["type"] == "swing_low"][-3:],
        "most_recent_shift": shifts[-1] if shifts else None,
    }


def _level_status(bars: list[dict], price: float, since_date: str, side: str) -> str:
    """OPEN / TESTED / SWEPT for a reference level: SWEPT if later price
    fully broke past it; TESTED if a wick came within 0.15% without a
    close breaking it; otherwise OPEN. Never deletes/guesses — only ever
    reads real bars after `since_date`."""
    after = [b for b in bars if b["datetime"] > since_date]
    if not after:
        return "OPEN"
    if side == "buy":
        if any(b["high"] > price for b in after):
            return "SWEPT"
        if any(b["high"] >= price * 0.9985 for b in after):
            return "TESTED"
        return "OPEN"
    if any(b["low"] < price for b in after):
        return "SWEPT"
    if any(b["low"] <= price * 1.0015 for b in after):
        return "TESTED"
    return "OPEN"


def _open_float_window(bars: list[dict], current_price: float, window: int) -> dict:
    if len(bars) < window:
        return {"status": "INSUFFICIENT DATA"}

    segment = bars[-window:]
    high_bar = max(segment, key=lambda b: b["high"])
    low_bar = min(segment, key=lambda b: b["low"])

    buy = _distance(current_price, high_bar["high"])
    sell = _distance(current_price, low_bar["low"])

    return {
        "high": high_bar["high"],
        "low": low_bar["low"],
        "buy_stops": {
            "level": high_bar["high"],
            "date": high_bar["datetime"],
            **buy,
            "status": _level_status(bars, high_bar["high"], high_bar["datetime"], "buy"),
        },
        "sell_stops": {
            "level": low_bar["low"],
            "date": low_bar["datetime"],
            **sell,
            "status": _level_status(bars, low_bar["low"], low_bar["datetime"], "sell"),
        },
    }


def _old_high_low(bars: list[dict], current_price: float) -> dict:
    """The primary IPDA range's high/low, distinct from any shorter
    swing — the institutional "old price high/low" reference points."""
    if not bars:
        return {"old_high": "Data unavailable", "old_low": "Data unavailable"}

    high_bar = max(bars, key=lambda b: b["high"])
    low_bar = min(bars, key=lambda b: b["low"])
    return {
        "old_high": {
            "price": high_bar["high"],
            "datetime": high_bar["datetime"],
            **_distance(current_price, high_bar["high"]),
            "status": _level_status(bars, high_bar["high"], high_bar["datetime"], "buy"),
        },
        "old_low": {
            "price": low_bar["low"],
            "datetime": low_bar["datetime"],
            **_distance(current_price, low_bar["low"]),
            "status": _level_status(bars, low_bar["low"], low_bar["datetime"], "sell"),
        },
    }


def _order_blocks_and_fvgs(bars: list[dict], current_price: float) -> dict:
    swings = detect_swings(bars, window=min(3, (len(bars) - 1) // 2) or 1)
    shifts = detect_market_structure_shifts(bars, swings)
    order_blocks = detect_order_blocks(bars, shifts)
    fvgs = detect_fair_value_gaps(bars)

    def _shape_ob(ob: dict) -> dict:
        side = "buy" if ob["direction"] == "bullish" else "sell"
        return {
            **ob,
            **_distance(current_price, ob["price"]),
            "mitigation_status": _level_status(bars, ob["price"], ob["datetime"], side),
        }

    def _shape_fvg(fvg: dict) -> dict:
        side = "buy" if fvg["direction"] == "bullish" else "sell"
        filled = _level_status(bars, fvg["price"], fvg["datetime"], side) != "OPEN"
        return {**fvg, **_distance(current_price, fvg["price"]), "filled": filled}

    bullish_obs = [_shape_ob(ob) for ob in order_blocks if ob["direction"] == "bullish"][-5:]
    bearish_obs = [_shape_ob(ob) for ob in order_blocks if ob["direction"] == "bearish"][-5:]
    gaps = [_shape_fvg(g) for g in fvgs][-8:]

    return {"bullish_order_blocks": bullish_obs, "bearish_order_blocks": bearish_obs, "fair_value_gaps": gaps}


def _cast_forward(last_shift: dict | None) -> dict:
    if not last_shift:
        return {w: "INSUFFICIENT DATA" for w in ("20d", "40d", "60d")} | {"three_month_limit": "INSUFFICIENT DATA"}

    anchor = _bar_date(last_shift)
    windows = {}
    for w in TRADING_DAY_WINDOWS:
        calendar_days = round(w * CALENDAR_DAYS_PER_TRADING_DAY)
        windows[f"{w}d"] = {
            "trading_days_from_shift": w,
            "estimated_date": (anchor + timedelta(days=calendar_days)).strftime("%Y-%m-%d"),
            "note": "Projected time window, not a price target or guaranteed date",
        }
    three_month_days = round(63 * CALENDAR_DAYS_PER_TRADING_DAY)
    windows["three_month_limit"] = {
        "trading_days_from_shift": 63,
        "estimated_date": (anchor + timedelta(days=three_month_days)).strftime("%Y-%m-%d"),
        "note": "Outer projection boundary — 3-month limit from the last major shift",
    }
    return windows


def _interpretation(direction: str, smart_money: dict, cast_forward: dict) -> str:
    parts = [f"Quarterly structure is currently {direction}."]
    if smart_money["buy_program"]:
        parts.append(f"{len(smart_money['buy_program'])} buy-program pattern(s) detected against the benchmark.")
    if smart_money["sell_program"]:
        parts.append(f"{len(smart_money['sell_program'])} sell-program pattern(s) detected against the benchmark.")
    if not smart_money["buy_program"] and not smart_money["sell_program"]:
        parts.append("No smart-money accumulation/distribution pattern currently confirmed against the benchmark.")
    if isinstance(cast_forward.get("20d"), dict):
        parts.append(f"Next projected window opens around {cast_forward['20d']['estimated_date']} (20 trading days).")
    return " ".join(parts)


async def get_ipda_data_ranges(symbol: str) -> dict:
    bars = await get_stored_bars(symbol, days_back=400)
    if len(bars) < PRIMARY_RANGE_SESSIONS:
        return {"symbol": symbol, "error": "INSUFFICIENT DATA"}

    current_price = bars[-1]["close"]
    primary_range_bars = bars[-PRIMARY_RANGE_SESSIONS:]

    benchmark_symbol = BENCHMARK_MAP.get(symbol)
    benchmark_bars = await _benchmark_bars(benchmark_symbol, PRIMARY_RANGE_SESSIONS + 20) if benchmark_symbol else []
    benchmark_available = len(benchmark_bars) >= 10

    # IPDA primary range
    range_high = max(b["high"] for b in primary_range_bars)
    range_low = min(b["low"] for b in primary_range_bars)
    ipda_range = {
        "start": primary_range_bars[0]["datetime"],
        "end": primary_range_bars[-1]["datetime"],
        "trading_days": PRIMARY_RANGE_SESSIONS,
        "high": range_high,
        "low": range_low,
    }

    # Smart money accumulation/distribution
    if benchmark_available:
        u_window = min(len(primary_range_bars), len(benchmark_bars))
        underlying_swings = _label_swings(
            detect_swings(primary_range_bars[-u_window:], window=min(3, (u_window - 1) // 2) or 1)
        )
        benchmark_swings = _label_swings(
            detect_swings(benchmark_bars[-u_window:], window=min(3, (u_window - 1) // 2) or 1)
        )
        smart_money = _smart_money_programs(underlying_swings, benchmark_swings)
        manipulation = _detect_manipulation(primary_range_bars, benchmark_bars)
        if manipulation:
            (smart_money["buy_program"] if manipulation["direction"] == "bullish" else smart_money["sell_program"]).insert(
                0, manipulation
            )
    else:
        smart_money = {"buy_program": "BENCHMARK DATA UNAVAILABLE", "sell_program": "BENCHMARK DATA UNAVAILABLE"}

    # Quarterly shift at 20/40/60D
    quarterly_shift = {f"{w}d": _window_analysis(bars, w) for w in TRADING_DAY_WINDOWS}
    swings_full = detect_swings(primary_range_bars, window=min(3, (len(primary_range_bars) - 1) // 2) or 1)
    all_shifts = detect_market_structure_shifts(primary_range_bars, swings_full)
    last_major_shift = all_shifts[-1] if all_shifts else None
    quarterly_shift["last_major_shift"] = last_major_shift
    quarterly_direction = last_major_shift["direction"] if last_major_shift else "neutral"

    # Institutional reference points
    reference_points = _order_blocks_and_fvgs(primary_range_bars, current_price)
    old_levels = _old_high_low(primary_range_bars, current_price)
    reference_points["old_highs"] = [old_levels["old_high"]]
    reference_points["old_lows"] = [old_levels["old_low"]]

    # Cast forward
    cast_forward = _cast_forward(last_major_shift)

    # Open Float at 20/40/60D
    open_float = {
        "near_term_20d": _open_float_window(bars, current_price, 20),
        "short_term_40d": _open_float_window(bars, current_price, 40),
        "intermediate_60d": _open_float_window(bars, current_price, 60),
    }

    result = {
        "symbol": symbol,
        "benchmark": benchmark_symbol if benchmark_available else "BENCHMARK DATA UNAVAILABLE",
        "current_price": current_price,
        "as_of": bars[-1]["datetime"],
        "ipda_range": ipda_range,
        "smart_money": smart_money,
        "quarterly_shift": quarterly_shift,
        "institutional_reference_points": reference_points,
        "previous_market_shift": last_major_shift,
        "cast_forward": cast_forward,
        "open_float": open_float,
        "interpretation": _interpretation(quarterly_direction, smart_money if benchmark_available else {"buy_program": [], "sell_program": []}, cast_forward),
    }
    return _safe_json(result)
