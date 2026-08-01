"""Tests for the Treasury Intelligence Engine.

Uses respx to intercept httpx calls, so this suite needs no network access
and no real FRED key — it runs the same in CI, locally, or in a sandboxed
environment. Run with: pytest backend/tests -v
"""
import httpx
import pytest
import respx

from app.services import treasury_service


@pytest.fixture(autouse=True)
def fred_api_key(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    treasury_service.get_settings.cache_clear()
    yield
    treasury_service.get_settings.cache_clear()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_fred_series_drops_missing_observations():
    route = respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2026-07-01", "value": "4.25"},
                    {"date": "2026-07-02", "value": "."},  # market holiday — FRED marks it "."
                    {"date": "2026-07-03", "value": "4.30"},
                ]
            },
        )
    )

    result = await treasury_service._fetch_fred_series("DGS10", days_back=10)

    assert route.called
    assert result == [
        {"date": "2026-07-01", "value": 4.25},
        {"date": "2026-07-03", "value": 4.30},
    ]


@respx.mock
@pytest.mark.asyncio
async def test_fetch_fred_series_raises_on_http_error():
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(400, json={"error_message": "Bad Request."})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await treasury_service._fetch_fred_series("DGS10")


def test_all_series_have_no_overlapping_labels():
    # Guards against a copy-paste bug where a spread label collides with a
    # yield label — get_yield_curve() relies on these being disjoint keys.
    assert set(treasury_service.TREASURY_SERIES) & set(treasury_service.SPREAD_SERIES) == set()
