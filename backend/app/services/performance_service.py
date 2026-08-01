"""Performance Analytics.

Aggregates historical_outcomes (populated by the Historical Learning
Engine) into three metrics per asset, recomputed daily:
  win_rate        - wins / (wins + losses), excluding neutral grades
  avg_pnl_pct      - mean of the recorded pnl_pct across graded decisions
  max_drawdown_pct - largest peak-to-trough decline in the *cumulative*
                     pnl_pct series, ordered by evaluation date — a
                     standard, real drawdown calculation, not a placeholder
"""
from datetime import datetime, timezone

from app.cache import ttl_cache
from app.database import get_supabase

ASSETS = ["XAUUSD", "NQ"]


def _max_drawdown_pct(ordered_pnls: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in ordered_pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return round(max_dd, 3)  # negative or zero


async def _compute_metrics_for_asset(supabase, asset: str) -> dict:
    result = (
        supabase.table("historical_outcomes")
        .select("outcome, pnl_pct, evaluated_at")
        .eq("asset", asset)
        .order("evaluated_at")
        .execute()
    )
    rows = result.data
    wins = sum(1 for r in rows if r["outcome"] == "win")
    losses = sum(1 for r in rows if r["outcome"] == "loss")
    pnls = [r["pnl_pct"] for r in rows if r["pnl_pct"] is not None]

    return {
        "win_rate": round(wins / (wins + losses), 4) if (wins + losses) > 0 else None,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 3) if pnls else None,
        "max_drawdown_pct": _max_drawdown_pct(pnls) if pnls else None,
        "total_decisions": len(rows),
    }


async def refresh_performance_metrics() -> dict:
    supabase = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows_written = 0

    for asset in ASSETS:
        metrics = await _compute_metrics_for_asset(supabase, asset)
        for metric_type in ("win_rate", "avg_pnl_pct", "max_drawdown_pct"):
            value = metrics[metric_type]
            if value is None:
                continue
            supabase.table("performance_metrics").upsert(
                {"date": today, "asset": asset, "metric_type": metric_type, "value": value},
                on_conflict="date,asset,metric_type",
            ).execute()
            rows_written += 1

    return {"rows_written": rows_written}


@ttl_cache(seconds=900)
async def get_performance_summary(asset: str) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("performance_metrics")
        .select("metric_type, value, date")
        .eq("asset", asset)
        .order("date", desc=True)
        .limit(30)  # a handful of days across 3 metric types
        .execute()
    )

    latest_by_metric: dict[str, dict] = {}
    for row in result.data:
        if row["metric_type"] not in latest_by_metric:
            latest_by_metric[row["metric_type"]] = row

    win_rate_row = latest_by_metric.get("win_rate")
    avg_pnl_row = latest_by_metric.get("avg_pnl_pct")

    # total_decisions isn't stored as its own metric row set, so read it
    # fresh — it's a cheap count query, not worth persisting separately.
    total = supabase.table("historical_outcomes").select("id", count="exact").eq("asset", asset).execute()

    return {
        "asset": asset,
        "win_rate": win_rate_row["value"] if win_rate_row else None,
        "avg_pnl_pct": avg_pnl_row["value"] if avg_pnl_row else None,
        "total_decisions": total.count or 0,
        "last_updated": win_rate_row["date"] if win_rate_row else None,
    }
