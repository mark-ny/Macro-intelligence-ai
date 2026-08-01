"""Tests for ICT pattern detection. Pure functions over plain dicts, no
network or Supabase needed — these test the algorithms in isolation."""
from app.services import ict_service


def _bar(dt, o, h, l, c):
    return {"datetime": dt, "open": o, "high": h, "low": l, "close": c}


def test_bullish_fair_value_gap_detected_between_candles_1_and_3():
    bars = [
        _bar("2026-01-01", 100, 102, 99, 101),   # candle 1: high = 102
        _bar("2026-01-02", 101, 108, 100, 107),   # candle 2: the gap candle
        _bar("2026-01-03", 107, 110, 104, 109),   # candle 3: low = 104 > candle 1 high (102) -> bullish FVG
    ]
    gaps = ict_service.detect_fair_value_gaps(bars)
    assert len(gaps) == 1
    assert gaps[0]["direction"] == "bullish"
    assert gaps[0]["price"] == (104 + 102) / 2


def test_bearish_fair_value_gap_detected_between_candles_1_and_3():
    bars = [
        _bar("2026-01-01", 110, 111, 108, 109),   # candle 1: low = 108
        _bar("2026-01-02", 109, 110, 100, 101),   # candle 2: the gap candle
        _bar("2026-01-03", 101, 103, 95, 97),     # candle 3: high = 103 < candle 1 low (108) -> bearish FVG
    ]
    gaps = ict_service.detect_fair_value_gaps(bars)
    assert len(gaps) == 1
    assert gaps[0]["direction"] == "bearish"


def test_no_fair_value_gap_when_candles_overlap():
    bars = [
        _bar("2026-01-01", 100, 105, 98, 102),
        _bar("2026-01-02", 102, 106, 99, 104),
        _bar("2026-01-03", 104, 107, 101, 105),  # low 101 < candle 1 high 105 -> overlap, no gap
    ]
    assert ict_service.detect_fair_value_gaps(bars) == []


def test_swing_high_detected_with_three_bars_either_side():
    # Bar index 3 is a clean peak: strictly higher than the 3 bars on each side.
    highs = [100, 101, 102, 110, 103, 102, 101]
    bars = [_bar(f"2026-01-0{i+1}", h - 2, h, h - 3, h - 1) for i, h in enumerate(highs)]
    swings = ict_service.detect_swings(bars, window=3)
    swing_highs = [s for s in swings if s["type"] == "swing_high"]
    assert len(swing_highs) == 1
    assert swing_highs[0]["index"] == 3
    assert swing_highs[0]["price"] == 110


def test_market_structure_shift_fires_when_close_breaks_prior_swing_high():
    # Same peak as above; the last bar's high of 112 gives it a close of
    # 111 (close = high - 1 in this helper), which breaks above the 110
    # swing high recorded at index 3 -> bullish MSS.
    highs = [100, 101, 102, 110, 103, 102, 101, 105, 112]
    bars = [_bar(f"2026-01-{i+1:02d}", h - 2, h, h - 3, h - 1) for i, h in enumerate(highs)]

    swings = ict_service.detect_swings(bars, window=3)
    shifts = ict_service.detect_market_structure_shifts(bars, swings)
    bullish_shifts = [s for s in shifts if s["direction"] == "bullish"]
    assert len(bullish_shifts) == 1
    assert bullish_shifts[0]["price"] == 110
