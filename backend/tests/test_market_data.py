from app.services.market_data_service import resample_bars


def _bar(dt, o, h, l, c):
    return {"datetime": dt, "open": o, "high": h, "low": l, "close": c}


def test_resample_weekly_groups_by_iso_week():
    # Mon 2026-01-05 through Fri 2026-01-09 is one ISO week; Mon 2026-01-12
    # starts the next one.
    bars = [
        _bar("2026-01-05", 100, 105, 99, 103),
        _bar("2026-01-06", 103, 106, 101, 104),
        _bar("2026-01-07", 104, 110, 103, 108),  # week 1 high
        _bar("2026-01-08", 108, 109, 95, 96),    # week 1 low
        _bar("2026-01-09", 96, 100, 94, 99),     # week 1 close
        _bar("2026-01-12", 99, 101, 97, 100),    # week 2
    ]
    weekly = resample_bars(bars, "1W")

    assert len(weekly) == 2
    week1 = weekly[0]
    assert week1["open"] == 100        # first day's open
    assert week1["high"] == 110        # max high across the week
    assert week1["low"] == 94          # min low across the week
    assert week1["close"] == 99        # last day's close
    assert week1["datetime"] == "2026-01-09"  # last bar's date represents the period


def test_resample_monthly_groups_by_calendar_month():
    bars = [
        _bar("2026-01-15", 100, 102, 98, 101),
        _bar("2026-01-30", 101, 115, 100, 110),  # January high
        _bar("2026-02-02", 110, 111, 90, 95),    # February — new group
    ]
    monthly = resample_bars(bars, "1M")

    assert len(monthly) == 2
    assert monthly[0]["high"] == 115
    assert monthly[0]["close"] == 110
    assert monthly[1]["open"] == 110
    assert monthly[1]["low"] == 90


def test_resample_1d_passthrough():
    bars = [_bar("2026-01-01", 1, 2, 0, 1)]
    assert resample_bars(bars, "1D") is bars
