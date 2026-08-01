from app.services.big_picture_service import _classify_inflation_regime, _cpi_yoy_series


def test_cpi_yoy_series_computes_year_over_year_pct_change():
    # A flat 300 -> 303 (1% YoY) between Jan 2025 and Jan 2026, with the
    # rest of 2025 present so the "12 months back" lookup has something
    # to find for the second point too.
    rows = [
        {"date": "2025-01-01", "value": 300.0},
        {"date": "2025-06-01", "value": 301.5},
        {"date": "2026-01-01", "value": 303.0},
        {"date": "2026-06-01", "value": 306.0},  # vs 301.5 a year earlier -> ~1.49%
    ]
    yoy = _cpi_yoy_series(rows)

    assert len(yoy) == 2  # only points with a match ~12 months back qualify
    assert yoy[0]["date"] == "2026-01-01"
    assert round(yoy[0]["yoy_pct"], 2) == 1.0
    assert round(yoy[1]["yoy_pct"], 2) == 1.49


def test_inflationary_when_yoy_accelerating():
    # Four readings, each 12%/13%/14%/16% oldest to newest -> latest (16)
    # is higher than 3-readings-ago (12) and positive -> inflationary.
    yoy = [{"date": f"2026-0{i}-01", "yoy_pct": v} for i, v in enumerate([1.2, 1.3, 1.4, 1.6], start=1)]
    regime, latest = _classify_inflation_regime(yoy)
    assert regime == "inflationary"
    assert latest == 1.6


def test_disinflationary_when_positive_but_decelerating():
    yoy = [{"date": f"2026-0{i}-01", "yoy_pct": v} for i, v in enumerate([4.0, 3.5, 3.0, 2.5], start=1)]
    regime, latest = _classify_inflation_regime(yoy)
    assert regime == "disinflationary"
    assert latest == 2.5


def test_deflationary_when_yoy_negative():
    yoy = [{"date": f"2026-0{i}-01", "yoy_pct": v} for i, v in enumerate([1.0, 0.5, -0.2, -0.8], start=1)]
    regime, latest = _classify_inflation_regime(yoy)
    assert regime == "deflationary"


def test_none_when_not_enough_history():
    assert _classify_inflation_regime([{"date": "2026-01-01", "yoy_pct": 2.0}]) == (None, None)
