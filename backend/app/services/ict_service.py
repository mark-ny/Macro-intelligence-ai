"""ICT Analysis Engine.

Reads OHLC bars from market_prices (populated by
market_data_service.refresh_market_prices) rather than calling Twelve
Data directly — see that module's docstring for why. Gold trades under
the symbol XAU/USD; NQ is proxied with QQQ, since real futures data is a
paid feed on every free tier we checked (see ASSET_SYMBOLS in
market_data_service.py).

Timeframe: daily bars. Free-tier request budgets make frequent intraday
polling impractical without a paid plan — this is a deliberate scope
choice, not an oversight.

The detectors below implement well-known ICT ("Inner Circle Trader")
price-action concepts as plain, inspectable functions over OHLC bars:
  - swing highs/lows      (fractal pivot points)
  - fair value gaps       (3-candle imbalance)
  - liquidity sweeps      (wick through a prior swing that closes back inside)
  - market structure shift (close breaking a prior swing high/low)
  - order blocks          (last opposite-colored candle before a structure shift)
These are heuristic pattern definitions, the same ones widely taught under
the ICT methodology — not a promise that the pattern predicts what happens
next. detect_swings() and detect_market_structure_shifts() are reused
directly by the Top-Down Analysis feature (topdown_service.py) to run the
same logic on resampled weekly/monthly bars.
"""
from app.cache import ttl_cache
from app.database import get_supabase
from app.services.market_data_service import ASSET_SYMBOLS, get_stored_bars

SWING_WINDOW = 3  # bars required on each side to confirm a pivot


def detect_swings(bars: list[dict], window: int = SWING_WINDOW) -> list[dict]:
    """Fractal swing highs/lows: a pivot needs `window` bars on both sides
    that are all lower (swing high) or all higher (swing low)."""
    swings = []
    for i in range(window, len(bars) - window):
        left, right = bars[i - window : i], bars[i + 1 : i + 1 + window]

        if all(bars[i]["high"] > b["high"] for b in left + right):
            swings.append({"index": i, "type": "swing_high", "price": bars[i]["high"], "datetime": bars[i]["datetime"]})
        elif all(bars[i]["low"] < b["low"] for b in left + right):
            swings.append({"index": i, "type": "swing_low", "price": bars[i]["low"], "datetime": bars[i]["datetime"]})

    return swings


def detect_fair_value_gaps(bars: list[dict]) -> list[dict]:
    """3-candle imbalance: candle i-1 and i+1 don't overlap, leaving a gap
    candle i's range didn't fill."""
    gaps = []
    for i in range(1, len(bars) - 1):
        prev_bar, next_bar = bars[i - 1], bars[i + 1]
        if next_bar["low"] > prev_bar["high"]:
            gaps.append({
                "type": "fair_value_gap", "direction": "bullish",
                "price": (next_bar["low"] + prev_bar["high"]) / 2,
                "datetime": bars[i]["datetime"],
                "notes": f"Gap between {prev_bar['high']:.2f} and {next_bar['low']:.2f}",
            })
        elif next_bar["high"] < prev_bar["low"]:
            gaps.append({
                "type": "fair_value_gap", "direction": "bearish",
                "price": (next_bar["high"] + prev_bar["low"]) / 2,
                "datetime": bars[i]["datetime"],
                "notes": f"Gap between {next_bar['high']:.2f} and {prev_bar['low']:.2f}",
            })
    return gaps


def detect_liquidity_sweeps(bars: list[dict], swings: list[dict]) -> list[dict]:
    """A bar wicks beyond the most recent prior swing high/low but closes
    back inside it — a classic ICT "stop hunt" before reversal."""
    sweeps = []
    prior_swing_high = prior_swing_low = None

    swing_by_index = {s["index"]: s for s in swings}
    for i, bar in enumerate(bars):
        if i in swing_by_index:
            s = swing_by_index[i]
            if s["type"] == "swing_high":
                prior_swing_high = s["price"]
            else:
                prior_swing_low = s["price"]
            continue

        if prior_swing_high is not None and bar["high"] > prior_swing_high and bar["close"] < prior_swing_high:
            sweeps.append({
                "type": "liquidity_sweep", "direction": "bearish", "price": prior_swing_high,
                "datetime": bar["datetime"],
                "notes": f"Wicked above {prior_swing_high:.2f}, closed back below",
            })
        if prior_swing_low is not None and bar["low"] < prior_swing_low and bar["close"] > prior_swing_low:
            sweeps.append({
                "type": "liquidity_sweep", "direction": "bullish", "price": prior_swing_low,
                "datetime": bar["datetime"],
                "notes": f"Wicked below {prior_swing_low:.2f}, closed back above",
            })
    return sweeps


def classify_market_structure(swings: list[dict]) -> dict:
    """
    Classifies the latest confirmed market structure.

    Returns:
        trend
        hh
        hl
        lh
        ll
        bos
        choch
        mss
        strength
    """

    highs = [s for s in swings if s["type"] == "swing_high"]
    lows = [s for s in swings if s["type"] == "swing_low"]

    if len(highs) < 2 or len(lows) < 2:
        return {
            "trend": "UNKNOWN",
            "hh": False,
            "hl": False,
            "lh": False,
            "ll": False,
            "bos": False,
            "choch": False,
            "mss": False,
            "strength": 0,
        }

    last_high = highs[-1]["price"]
    prev_high = highs[-2]["price"]

    last_low = lows[-1]["price"]
    prev_low = lows[-2]["price"]

    hh = last_high > prev_high
    hl = last_low > prev_low

    lh = last_high < prev_high
    ll = last_low < prev_low

    trend = "RANGE"

    if hh and hl:
        trend = "BULLISH"

    elif lh and ll:
        trend = "BEARISH"

    bos = (
        (trend == "BULLISH" and hh)
        or
        (trend == "BEARISH" and ll)
    )

    choch = (
        (hh and ll)
        or
        (lh and hl)
    )

    mss = choch

    strength = 50

    if trend != "RANGE":
        strength += 20

    if bos:
        strength += 10

    if choch:
        strength += 10

    if hh and hl:
        strength += 5

    if lh and ll:
        strength += 5

    strength = min(strength, 100)

    return {
        "trend": trend,
        "hh": hh,
        "hl": hl,
        "lh": lh,
        "ll": ll,
        "bos": bos,
        "choch": choch,
        "mss": mss,
        "strength": strength,
        "last_high": last_high,
        "last_low": last_low,
    }


def detect_order_blocks(bars: list[dict], shifts: list[dict]) -> list[dict]:
    """The last opposite-colored candle before a market structure shift —
    a simplified, widely used definition of an ICT order block."""
    blocks = []
    bars_by_datetime = {b["datetime"]: i for i, b in enumerate(bars)}

    for shift in shifts:
        shift_index = bars_by_datetime.get(shift["datetime"])
        if shift_index is None:
            continue

        wanted_color = "bearish" if shift["direction"] == "bullish" else "bullish"
        for j in range(shift_index - 1, max(shift_index - 10, -1), -1):
            candle = bars[j]
            color = "bullish" if candle["close"] >= candle["open"] else "bearish"
            if color == wanted_color:
                blocks.append({
                    "type": "order_block", "direction": shift["direction"],
                    "price": candle["low"] if shift["direction"] == "bullish" else candle["high"],
                    "datetime": candle["datetime"],
                    "notes": f"Last {wanted_color} candle before the {shift['datetime']} structure shift",
                })
                break

    return blocks

 def calculate_institutional_bias(
    structure: dict,
    signals: list[dict],
) -> dict:
    """
    Produces the overall institutional bias.

    Returns:
        bias
        confidence
        score
    """

    score = 0

    # -------------------------
    # Market Structure
    # -------------------------

    if structure["trend"] == "BULLISH":
        score += 40

    elif structure["trend"] == "BEARISH":
        score -= 40

    if structure["bos"]:
        score += 15 if structure["trend"] == "BULLISH" else -15

    if structure["choch"]:
        score += 10 if structure["trend"] == "BULLISH" else -10

    # -------------------------
    # Signal Scoring
    # -------------------------

    for signal in signals:

        if signal["type"] == "fair_value_gap":

            if signal["direction"] == "bullish":
                score += 4
            else:
                score -= 4

        elif signal["type"] == "liquidity_sweep":

            if signal["direction"] == "bullish":
                score += 8
            else:
                score -= 8

        elif signal["type"] == "order_block":

            if signal["direction"] == "bullish":
                score += 10
            else:
                score -= 10

        elif signal["type"] == "market_structure_shift":

            if signal["direction"] == "bullish":
                score += 12
            else:
                score -= 12

    # -------------------------
    # Final Bias
    # -------------------------

    if score >= 40:
        bias = "BUY"

    elif score <= -40:
        bias = "SELL"

    else:
        bias = "WAIT"

    confidence = min(abs(score), 100)

    return {
        "bias": bias,
        "confidence": confidence,
        "score": score,
    }


def _run_all_detectors(bars: list[dict]) -> tuple[list[dict], dict]:

    swings = detect_swings(bars)

    structure = classify_market_structure(swings)

    shifts = detect_market_structure_shifts(bars, swings)

    signals = [
        *detect_fair_value_gaps(bars),
        *detect_liquidity_sweeps(bars, swings),
        *shifts,
        *detect_order_blocks(bars, shifts),
    ]

    return signals, structure


async def refresh_ict_signals(lookback_bars: int = 150) -> dict:
    supabase = get_supabase()
    rows: list[dict] = []
    errors: dict[str, str] = {}

    for asset in ASSET_SYMBOLS:
        try:
            bars = await get_stored_bars(asset, days_back=lookback_bars * 2)  # calendar days, so bars comfortably cover lookback_bars trading days
            if len(bars) < 2 * SWING_WINDOW + 1:
                errors[asset] = "Not enough stored bars yet — run POST /api/market-data/refresh first."
                continue
            signals, structure = _run_all_detectors(bars)
          bias = calculate_institutional_bias(
              structure,
              signals,
        )
        except Exception as exc:  # noqa: BLE001
            errors[asset] = str(exc)
            continue

        for signal in signals:
            rows.append({

    "asset": asset,

    "timeframe": "1D",

    "signal_type": signal["type"],

    "direction": signal["direction"],

    "price_level": signal["price"],

    "detected_at": signal["datetime"],

    "notes": signal.get("notes"),

    "confidence": bias["confidence"],

    "institutional_bias": bias["bias"],

    "market_trend": structure["trend"],

    "trend_strength": structure["strength"],

})

    if rows:
        for i in range(0, len(rows), 500):
            supabase.table("ict_signals").upsert(
                rows[i : i + 500],
                on_conflict="asset,timeframe,signal_type,direction,detected_at",
            ).execute()

    return {"signals_inserted": len(rows), "assets_with_errors": errors}


@ttl_cache(seconds=900)
async def get_latest_signals(asset: str = "XAUUSD", limit: int = 20) -> list[dict]:
    if asset not in ASSET_SYMBOLS:
        raise ValueError(f"Unknown asset '{asset}'. Valid: {sorted(ASSET_SYMBOLS)}")

    supabase = get_supabase()
    result = (
        supabase.table("ict_signals")
        .select("*")
        .eq("asset", asset)
        .order("detected_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
