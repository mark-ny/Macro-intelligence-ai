"""DXY Forecast Engine.

Data source: FRED series DTWEXBGS (Trade Weighted U.S. Dollar Index: Broad,
Goods and Services) — a daily, official proxy for dollar strength. This is
NOT the same weighting ICE uses for the tradable "DXY" future (that feed is
a paid market-data product), but it tracks the same underlying idea — the
dollar against a broad basket — and is completely free.

Forecast methodology (deliberately simple and disclosed, not a black box):
an ordinary-least-squares trend line fit to the last `days_back` daily
values, extrapolated `horizon_days` forward. The confidence band comes
from the residual standard deviation of the fit, not a proper prediction
interval — it is a rough band, not a statistical guarantee. This is a
naive-drift model, the same starting point any real forecasting effort
would be benchmarked against, not a claim of predictive power.
"""
from datetime import datetime, timedelta, timezone

import numpy as np

from app.cache import ttl_cache
from app.database import get_supabase
from app.services.treasury_service import _fetch_fred_series

DXY_SERIES_ID = "DTWEXBGS"

# Over the forecast horizon, how much the index needs to move (in index
# points) before we call it a trend rather than "flat".
TREND_THRESHOLD = 0.3


async def refresh_dxy_data(days_back: int = 400) -> dict:
    supabase = get_supabase()
    observations = await _fetch_fred_series(DXY_SERIES_ID, days_back=days_back)

    rows = [{"date": obs["date"], "value": obs["value"], "source": "FRED_DTWEXBGS"} for obs in observations]
    if rows:
        for i in range(0, len(rows), 500):
            supabase.table("dxy_data").upsert(rows[i : i + 500], on_conflict="date").execute()

    forecast = None
    if len(observations) >= 10:
        forecast = _fit_and_store_forecast(supabase, observations)

    return {"rows_upserted": len(rows), "forecast_generated": forecast is not None}


def _fit_and_store_forecast(supabase, observations: list[dict], days_back: int = 60, horizon_days: int = 10) -> dict:
    recent = observations[-days_back:] if len(observations) > days_back else observations
    values = np.array([o["value"] for o in recent], dtype=float)
    x = np.arange(len(values), dtype=float)

    slope, intercept = np.polyfit(x, values, 1)
    fitted = slope * x + intercept
    residuals = values - fitted
    residual_std = float(residuals.std()) if len(residuals) > 1 else 0.0

    ss_res = float((residuals**2).sum())
    ss_tot = float(((values - values.mean()) ** 2).sum())
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    forecast_x = len(values) - 1 + horizon_days
    predicted = float(slope * forecast_x + intercept)
    band = 1.96 * residual_std

    move = predicted - values[-1]
    trend = "up" if move > TREND_THRESHOLD else "down" if move < -TREND_THRESHOLD else "flat"

    forecast = {
        "forecast_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "horizon_days": horizon_days,
        "predicted": predicted,
        "confidence": round(max(0.0, min(1.0, r_squared)), 4),
        "model_version": "ols-trend-v1",
        "lower_bound": predicted - band,
        "upper_bound": predicted + band,
        "trend": trend,
    }
    supabase.table("dxy_forecasts").insert(forecast).execute()

    return {**forecast, "r_squared": r_squared}


@ttl_cache(seconds=900)
async def get_dxy_snapshot() -> dict:
    supabase = get_supabase()

    latest_result = (
        supabase.table("dxy_data").select("date, value").order("date", desc=True).limit(1).execute()
    )
    latest = latest_result.data[0] if latest_result.data else None

    forecast_result = (
        supabase.table("dxy_forecasts")
        .select("*")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    stored_forecast = forecast_result.data[0] if forecast_result.data else None

    forecast_payload = None
    if stored_forecast:
        forecast_payload = {
            "horizon_days": stored_forecast["horizon_days"],
            "predicted_value": stored_forecast["predicted"],
            "lower_bound": stored_forecast.get("lower_bound"),
            "upper_bound": stored_forecast.get("upper_bound"),
            "trend": stored_forecast.get("trend"),
            "r_squared": stored_forecast.get("confidence", 0.0),
            "generated_at": stored_forecast["created_at"],
        }

    return {
        "latest_value": latest["value"] if latest else None,
        "latest_date": latest["date"] if latest else None,
        "forecast": forecast_payload,
    }


@ttl_cache(seconds=900)
async def get_dxy_history(days: int = 180) -> list[dict]:
    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    result = (
        supabase.table("dxy_data")
        .select("date, value")
        .gte("date", cutoff)
        .order("date")
        .execute()
    )
    return result.data
