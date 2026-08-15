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
from app.services.market_data_service import (
    ASSET_SYMBOLS,
    get_stored_bars,
)

SWING_WINDOW = 3

# How much history to run the detectors over on each refresh. Wide enough
# for meaningful swing/structure context, narrow enough that institutional
# bias reflects current conditions rather than every signal since 2020.
REFRESH_LOOKBACK_DAYS = 180

# Both tables upsert on a natural key (asset, timeframe, signal
# type/direction, detected_at) instead of always inserting, so re-running
# refresh_ict_signals() doesn't pile up duplicate rows for signals whose
# underlying bar data hasn't changed. ict_signals is a full upsert — every
# refresh overwrites the bias/trend/OTE context with the latest snapshot.
# reinforcement_learning instead upserts with ignore_duplicates=True so an
# already-graded record's status/reward is never reset back to PENDING.
_SIGNALS_CONFLICT_KEY = "asset,timeframe,signal_type,direction,detected_at"
_LEARNING_CONFLICT_KEY = "asset,timeframe,signal_type,signal_direction,detected_at"


# ============================================================
# SWING DETECTION
# ============================================================

def detect_swings(
    bars: list[dict],
    window: int = SWING_WINDOW,
) -> list[dict]:
    """
    Detect confirmed swing highs and swing lows using
    ICT fractal confirmation.
    """

    swings = []

    for i in range(window, len(bars) - window):

        left = bars[i - window:i]
        right = bars[i + 1:i + 1 + window]

        if all(
            bars[i]["high"] > x["high"]
            for x in left + right
        ):
            swings.append(
                {
                    "index": i,
                    "type": "swing_high",
                    "price": bars[i]["high"],
                    "datetime": bars[i]["datetime"],
                }
            )

        elif all(
            bars[i]["low"] < x["low"]
            for x in left + right
        ):
            swings.append(
                {
                    "index": i,
                    "type": "swing_low",
                    "price": bars[i]["low"],
                    "datetime": bars[i]["datetime"],
                }
            )

    return swings


# ============================================================
# FAIR VALUE GAPS
# ============================================================

def detect_fair_value_gaps(
    bars: list[dict],
) -> list[dict]:

    gaps = []

    for i in range(1, len(bars) - 1):

        previous = bars[i - 1]
        current = bars[i]
        nxt = bars[i + 1]

        if nxt["low"] > previous["high"]:

            gaps.append(
                {
                    "type": "fair_value_gap",
                    "direction": "bullish",
                    "price": (
                        previous["high"]
                        + nxt["low"]
                    ) / 2,
                    "high": nxt["low"],
                    "low": previous["high"],
                    "datetime": current["datetime"],
                    "notes": (
                        f"Gap between "
                        f"{previous['high']:.2f}"
                        f" and "
                        f"{nxt['low']:.2f}"
                    ),
                }
            )

        elif nxt["high"] < previous["low"]:

            gaps.append(
                {
                    "type": "fair_value_gap",
                    "direction": "bearish",
                    "price": (
                        previous["low"]
                        + nxt["high"]
                    ) / 2,
                    "high": previous["low"],
                    "low": nxt["high"],
                    "datetime": current["datetime"],
                    "notes": (
                        f"Gap between "
                        f"{nxt['high']:.2f}"
                        f" and "
                        f"{previous['low']:.2f}"
                    ),
                }
            )

    return gaps


# ============================================================
# LIQUIDITY SWEEPS
# ============================================================

def detect_liquidity_sweeps(
    bars: list[dict],
    swings: list[dict],
) -> list[dict]:

    sweeps = []

    previous_high = None
    previous_low = None

    swing_lookup = {
        s["index"]: s
        for s in swings
    }

    for i, candle in enumerate(bars):

        if i in swing_lookup:

            swing = swing_lookup[i]

            if swing["type"] == "swing_high":
                previous_high = swing["price"]
            else:
                previous_low = swing["price"]

            continue

        if (
            previous_high is not None
            and candle["high"] > previous_high
            and candle["close"] < previous_high
        ):

            sweeps.append(
                {
                    "type": "liquidity_sweep",
                    "direction": "bearish",
                    "price": previous_high,
                    "datetime": candle["datetime"],
                    "notes": (
                        f"Liquidity taken above "
                        f"{previous_high:.2f}"
                    ),
                }
            )

        if (
            previous_low is not None
            and candle["low"] < previous_low
            and candle["close"] > previous_low
        ):

            sweeps.append(
                {
                    "type": "liquidity_sweep",
                    "direction": "bullish",
                    "price": previous_low,
                    "datetime": candle["datetime"],
                    "notes": (
                        f"Liquidity taken below "
                        f"{previous_low:.2f}"
                    ),
                }
            )

    return sweeps


# ============================================================
# MARKET STRUCTURE
# ============================================================

def classify_market_structure(
    swings: list[dict],
) -> dict:

    highs = [
        x for x in swings
        if x["type"] == "swing_high"
    ]

    lows = [
        x for x in swings
        if x["type"] == "swing_low"
    ]

    if len(highs) < 2 or len(lows) < 2:

        return {
            "trend": "RANGE",
            "hh": False,
            "hl": False,
            "lh": False,
            "ll": False,
            "bos": False,
            "choch": False,
            "mss": False,
            "strength": 0,
            "last_high": None,
            "last_low": None,
        }

    last_high = highs[-1]["price"]
    previous_high = highs[-2]["price"]

    last_low = lows[-1]["price"]
    previous_low = lows[-2]["price"]

    hh = last_high > previous_high
    hl = last_low > previous_low

    lh = last_high < previous_high
    ll = last_low < previous_low

    trend = "RANGE"

    if hh and hl:
        trend = "BULLISH"

    elif lh and ll:
        trend = "BEARISH"

    bos = (
        trend == "BULLISH"
        and hh
    ) or (
        trend == "BEARISH"
        and ll
    )

    choch = (
        (hh and ll)
        or
        (lh and hl)
    )

    strength = 50

    if trend != "RANGE":
        strength += 20

    if bos:
        strength += 15

    if choch:
        strength += 15

    strength = min(strength, 100)

    return {
        "trend": trend,
        "hh": hh,
        "hl": hl,
        "lh": lh,
        "ll": ll,
        "bos": bos,
        "choch": choch,
        "mss": choch,
        "strength": strength,
        "last_high": last_high,
        "last_low": last_low,
    }

 # ============================================================
# MARKET STRUCTURE SHIFTS (BOS / CHOCH)
# ============================================================

def detect_market_structure_shifts(
    bars: list[dict],
    swings: list[dict],
) -> list[dict]:

    shifts = []

    previous_high = None
    previous_low = None

    swing_lookup = {
        s["index"]: s
        for s in swings
    }

    for i, candle in enumerate(bars):

        if i in swing_lookup:

            swing = swing_lookup[i]

            if swing["type"] == "swing_high":
                previous_high = swing["price"]
            else:
                previous_low = swing["price"]

            continue

        if (
            previous_high is not None
            and candle["close"] > previous_high
        ):

            shifts.append(
                {
                    "type": "market_structure_shift",
                    "direction": "bullish",
                    "price": previous_high,
                    "datetime": candle["datetime"],
                    "notes": f"Closed above {previous_high:.2f}",
                }
            )

            previous_high = None

        if (
            previous_low is not None
            and candle["close"] < previous_low
        ):

            shifts.append(
                {
                    "type": "market_structure_shift",
                    "direction": "bearish",
                    "price": previous_low,
                    "datetime": candle["datetime"],
                    "notes": f"Closed below {previous_low:.2f}",
                }
            )

            previous_low = None

    return shifts


# ============================================================
# ORDER BLOCKS
# ============================================================

def detect_order_blocks(
    bars: list[dict],
    shifts: list[dict],
) -> list[dict]:

    blocks = []

    lookup = {
        b["datetime"]: i
        for i, b in enumerate(bars)
    }

    for shift in shifts:

        index = lookup.get(
            shift["datetime"]
        )

        if index is None:
            continue

        wanted = (
            "bearish"
            if shift["direction"] == "bullish"
            else "bullish"
        )

        for j in range(
            index - 1,
            max(index - 10, -1),
            -1,
        ):

            candle = bars[j]

            color = (
                "bullish"
                if candle["close"] >= candle["open"]
                else "bearish"
            )

            if color != wanted:
                continue

            blocks.append(
                {
                    "type": "order_block",
                    "direction": shift["direction"],
                    "price": (
                        candle["low"]
                        if shift["direction"] == "bullish"
                        else candle["high"]
                    ),
                    "high": candle["high"],
                    "low": candle["low"],
                    "datetime": candle["datetime"],
                    "notes": (
                        f"Last {wanted} candle "
                        f"before structure shift"
                    ),
                }
            )

            break

    return blocks


# ============================================================
# DEALING RANGE
# ============================================================

def calculate_dealing_range(
    swings: list[dict],
):

    highs = [
        s for s in swings
        if s["type"] == "swing_high"
    ]

    lows = [
        s for s in swings
        if s["type"] == "swing_low"
    ]

    if not highs or not lows:
        return None

    high = highs[-1]["price"]
    low = lows[-1]["price"]

    equilibrium = (
        high + low
    ) / 2

    return {
        "high": high,
        "low": low,
        "equilibrium": equilibrium,
    }


# ============================================================
# ICT OTE
# ============================================================

def calculate_ote(
    dealing_range: dict,
):

    diff = (
        dealing_range["high"]
        - dealing_range["low"]
    )

    return {

        "buy_ote_low":
            dealing_range["high"] - diff * 0.79,

        "buy_ote_high":
            dealing_range["high"] - diff * 0.62,

        "sell_ote_low":
            dealing_range["low"] + diff * 0.62,

        "sell_ote_high":
            dealing_range["low"] + diff * 0.79,
    }


# ============================================================
# PREMIUM / DISCOUNT
# ============================================================

def classify_price_location(
    price: float,
    dealing_range: dict,
):

    if price > dealing_range["equilibrium"]:
        return "PREMIUM"

    if price < dealing_range["equilibrium"]:
        return "DISCOUNT"

    return "EQUILIBRIUM"


# ============================================================
# INSTITUTIONAL BIAS
# ============================================================

def calculate_institutional_bias(
    structure: dict,
    signals: list[dict],
):

    score = 0

    if structure["trend"] == "BULLISH":
        score += 40

    elif structure["trend"] == "BEARISH":
        score -= 40

    if structure["bos"]:
        score += (
            15
            if structure["trend"] == "BULLISH"
            else -15
        )

    if structure["choch"]:
        score += (
            10
            if structure["trend"] == "BULLISH"
            else -10
        )

    for signal in signals:

        value = 0

        if signal["type"] == "fair_value_gap":
            value = 4

        elif signal["type"] == "liquidity_sweep":
            value = 8

        elif signal["type"] == "order_block":
            value = 10

        elif signal["type"] == "market_structure_shift":
            value = 12

        if signal["direction"] == "bullish":
            score += value
        else:
            score -= value

    if score >= 40:
        bias = "BUY"

    elif score <= -40:
        bias = "SELL"

    else:
        bias = "WAIT"

    return {

        "bias": bias,

        "confidence": min(
            abs(score),
            100,
        ),

        "score": score,
    }

# ============================================================
# RUN ALL ICT DETECTORS
# ============================================================

def _run_all_detectors(
    bars: list[dict],
) -> tuple[list[dict], dict, dict | None]:

    swings = detect_swings(bars)

    structure = classify_market_structure(swings)

    dealing_range = calculate_dealing_range(swings)

    shifts = detect_market_structure_shifts(
        bars,
        swings,
    )

    signals = [
        *detect_fair_value_gaps(bars),
        *detect_liquidity_sweeps(
            bars,
            swings,
        ),
        *shifts,
        *detect_order_blocks(
            bars,
            shifts,
        ),
    ]

    return (
        signals,
        structure,
        dealing_range,
    )


# ============================================================
# REINFORCEMENT LEARNING RECORD
# ============================================================

def build_learning_record(
    asset: str,
    structure: dict,
    bias: dict,
    signal: dict,
) -> dict:

    return {

        "asset": asset,

        "timeframe": "1D",

        "prediction": bias["bias"],

        "confidence": bias["confidence"],

        "trend": structure["trend"],

        "trend_strength": structure["strength"],

        "bos": structure["bos"],

        "choch": structure["choch"],

        "mss": structure["mss"],

        "hh": structure["hh"],

        "hl": structure["hl"],

        "lh": structure["lh"],

        "ll": structure["ll"],

        "signal_type": signal["type"],

        "signal_direction": signal["direction"],

        "price": signal["price"],

        "detected_at": signal["datetime"],

        "status": "PENDING",

        "actual_direction": None,

        "result": None,

        "reward": 0.0,
    }


# ============================================================
# EVALUATE REINFORCEMENT LEARNING
# ============================================================

async def evaluate_learning_records(
    look_forward_bars: int = 10,
) -> dict:

    supabase = get_supabase()

    pending = (
        supabase
        .table("reinforcement_learning")
        .select("*")
        .eq("status", "PENDING")
        .execute()
        .data
    )

    evaluated = 0

    for record in pending:

        asset = record["asset"]

        bars = await get_stored_bars(
            asset,
            days_back=30,
        )

        if not bars:
            continue

        future = [
            bar
            for bar in bars
            if bar["datetime"] > record["detected_at"]
        ]

        if len(future) < look_forward_bars:
            continue

        future = future[:look_forward_bars]

        entry = record["price"]

        highest = max(
            x["high"]
            for x in future
        )

        lowest = min(
            x["low"]
            for x in future
        )

        prediction = record["prediction"]

        reward = 0.0

        result = "LOSS"

        actual = "RANGE"

        if prediction == "BUY":

            if highest > entry:

                reward = highest - entry

                result = "WIN"

                actual = "BUY"

            else:

                reward = lowest - entry

                actual = "SELL"

        elif prediction == "SELL":

            if lowest < entry:

                reward = entry - lowest

                result = "WIN"

                actual = "SELL"

            else:

                reward = entry - highest

                actual = "BUY"

        supabase.table(
            "reinforcement_learning"
        ).update(

            {

                "status": "COMPLETE",

                "reward": reward,

                "result": result,

                "actual_direction": actual,

            }

        ).eq(

            "id",
            record["id"],

        ).execute()

        evaluated += 1

    return {

        "evaluated": evaluated,

    }


# ============================================================
# SIGNAL ROW BUILDER (ict_signals table shape)
# ============================================================

def _build_signal_row(
    asset: str,
    timeframe: str,
    signal: dict,
    structure: dict,
    bias: dict,
    ote: dict | None,
    premium_discount: str | None,
) -> dict:
    """Shapes one detector signal into an ict_signals row. The
    structure/bias/OTE/premium-discount fields are the same for every
    signal produced by one refresh — they're the market context the
    signal was detected under, not per-signal values."""
    return {
        "asset": asset,
        "timeframe": timeframe,
        "signal_type": signal["type"],
        "direction": signal["direction"],
        "price_level": signal["price"],
        "detected_at": signal["datetime"],
        "notes": signal.get("notes"),
        "confidence": bias["confidence"],
        "institutional_bias": bias["bias"],
        "market_trend": structure["trend"],
        "trend_strength": structure["strength"],
        "premium_discount": premium_discount,
        "buy_ote_low": ote["buy_ote_low"] if ote else None,
        "buy_ote_high": ote["buy_ote_high"] if ote else None,
        "sell_ote_low": ote["sell_ote_low"] if ote else None,
        "sell_ote_high": ote["sell_ote_high"] if ote else None,
    }


# ============================================================
# REFRESH — run detectors, persist signals + RL records
# ============================================================

async def refresh_ict_signals(timeframe: str = "1D") -> dict:
    """Runs the full ICT detector suite for every tracked asset over the
    last REFRESH_LOOKBACK_DAYS of stored bars, then upserts:
      - one row per detected signal into ict_signals (with the
        institutional-bias/premium-discount/OTE context attached), and
      - one pending prediction per signal into reinforcement_learning,
        later graded by evaluate_learning_records().

    Both tables upsert on a natural key (asset, signal type/direction,
    detected_at) so re-running this on unchanged history is a no-op
    instead of piling up duplicate rows every scheduler tick.
    """
    supabase = get_supabase()
    results: dict[str, dict] = {}

    for asset in ASSET_SYMBOLS:
        bars = await get_stored_bars(asset, days_back=REFRESH_LOOKBACK_DAYS)

        if len(bars) < SWING_WINDOW * 2 + 1:
            results[asset] = {"signals": 0, "learning_records": 0, "note": "not enough bars yet"}
            continue

        signals, structure, dealing_range = _run_all_detectors(bars)
        bias = calculate_institutional_bias(structure, signals)
        ote = calculate_ote(dealing_range) if dealing_range else None
        premium_discount = (
            classify_price_location(bars[-1]["close"], dealing_range)
            if dealing_range
            else None
        )

        signal_rows = [
            _build_signal_row(asset, timeframe, signal, structure, bias, ote, premium_discount)
            for signal in signals
        ]
        learning_rows = [
            build_learning_record(asset, structure, bias, signal)
            for signal in signals
        ]

        # ict_signals: full upsert (ignore_duplicates NOT set) — every
        # refresh should overwrite the bias/trend/OTE context on existing
        # rows with the latest snapshot. Unlike reinforcement_learning
        # below, there's no "already graded" state here worth protecting.
        for i in range(0, len(signal_rows), 500):
            supabase.table("ict_signals").upsert(
                signal_rows[i : i + 500],
                on_conflict=_SIGNALS_CONFLICT_KEY,
            ).execute()

        # reinforcement_learning: ignore_duplicates=True — once a record
        # has been graded (status flips PENDING -> COMPLETE with a
        # reward/result), re-running refresh on the same historical
        # signal must NOT overwrite that grade back to a fresh PENDING.
        for i in range(0, len(learning_rows), 500):
            supabase.table("reinforcement_learning").upsert(
                learning_rows[i : i + 500],
                on_conflict=_LEARNING_CONFLICT_KEY,
                ignore_duplicates=True,
            ).execute()

        results[asset] = {
            "signals": len(signal_rows),
            "learning_records": len(learning_rows),
            "trend": structure["trend"],
            "institutional_bias": bias["bias"],
            "confidence": bias["confidence"],
            "premium_discount": premium_discount,
        }

    return {"timeframe": timeframe, "assets": results}


# ============================================================
# GET LATEST SIGNALS
# ============================================================

@ttl_cache(seconds=900)
async def get_latest_signals(asset: str, limit: int = 20) -> list[dict]:
    """Most recent persisted ict_signals rows for an asset, newest first —
    what GET /api/ict/signals and the ICT analysis page read."""
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
