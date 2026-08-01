from app.services.short_term_service import _classify_position


def test_beyond_high_when_close_exceeds_range():
    assert _classify_position(close=110, range_high=105, range_low=95) == "beyond_high"


def test_beyond_low_when_close_below_range():
    assert _classify_position(close=90, range_high=105, range_low=95) == "beyond_low"


def test_at_high_when_within_tolerance_of_range_high():
    # range_high=105, tolerance 0.1% -> anything >= 104.895 and <= 105 counts as "at_high"
    assert _classify_position(close=104.9, range_high=105, range_low=95) == "at_high"


def test_at_low_when_within_tolerance_of_range_low():
    assert _classify_position(close=95.05, range_high=105, range_low=95) == "at_low"


def test_inside_when_comfortably_within_range():
    assert _classify_position(close=100, range_high=105, range_low=95) == "inside"
