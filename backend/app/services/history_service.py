"""Historical Learning Engine.

Evaluates AI Decision Engine calls that are old enough to judge (default:
5 trading days) against what price actually did afterward, using the same
Twelve Data OHLC feed the ICT engine already pulls — reused here rather
than adding a second market-data path.

Outcome logic, per decision:
  long    -> win if price rose since the decision, loss if it fell
  short   -> win if price fell since the decision, loss if it rose
  neutral -> no directional bet was made, so it's recorded as "neutral",
             never as a win or loss
A small dead-band (FLAT_THRESHOLD_PCT) below which a move counts as
"neutral" rather than a coin-flip win/loss, since a 0.02% wiggle isn't a
meaningful test of the decision.
"""
from datetime import datetime, timedelta, timezone

from app.cache import ttl_cache
from app.database import get_supabase
from app.services.market_data_service import get_stored_bars

EVALUATION_HORIZON_DAYS = 5
FLAT_THRESHOLD_PCT = 0.1


def _closest_close_on_or_after(bars: list[dict], target: datetime) -> float | None:
    target_str = target.strftime("%Y-%m-%d")
    for bar in bars:  # bars are ascending by date
        if bar["datetime"][:10] >= target_str:
            return bar["close"]
    return None


async def evaluate_pending_decisions(horizon_days: int = EVALUATION_HORIZON_DAYS) -> dict:
    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=horizon_days)).isoformat()

    pending = (
        supabase.table("ai_decisions")
        .select("id, asset, decision, created_at")
        .eq("outcome_evaluated", False)
        .lte("created_at", cutoff)
        .execute()
    )

    if not pending.data:
        return {"evaluated": 0}

    bars_by_asset: dict[str, list[dict]] = {}
    evaluated = 0

    for row in pending.data:
        asset = row["asset"]
        if asset not in bars_by_asset:
            try:
                bars_by_asset[asset] = await get_stored_bars(asset, days_back=400)
            except Exception:  # noqa: BLE001 — skip this asset's batch if the store is empty
                bars_by_asset[asset] = []

        bars = bars_by_asset[asset]
        if not bars:
            continue

        decided_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        entry_price = _closest_close_on_or_after(bars, decided_at)
        current_price = bars[-1]["close"]
        if entry_price is None or entry_price == 0:
            continue

        pct_change = (current_price - entry_price) / entry_price * 100

        if row["decision"] == "neutral" or abs(pct_change) < FLAT_THRESHOLD_PCT:
            outcome = "neutral"
        elif row["decision"] == "long":
            outcome = "win" if pct_change > 0 else "loss"
        else:  # "short"
            outcome = "win" if pct_change < 0 else "loss"

        supabase.table("historical_outcomes").insert({
            "decision_id": row["id"],
            "asset": asset,
            "outcome": outcome,
            "pnl_pct": round(pct_change, 3),
        }).execute()
        supabase.table("ai_decisions").update({"outcome_evaluated": True}).eq("id", row["id"]).execute()
        evaluated += 1

    return {"evaluated": evaluated}


@ttl_cache(seconds=900)
async def get_outcomes(asset: str, limit: int = 20) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("historical_outcomes")
        .select("*")
        .eq("asset", asset)
        .order("evaluated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@ttl_cache(seconds=900)
async def get_win_rate(asset: str) -> dict:
    supabase = get_supabase()
    result = supabase.table("historical_outcomes").select("outcome").eq("asset", asset).execute()

    total = len(result.data)
    wins = sum(1 for r in result.data if r["outcome"] == "win")
    losses = sum(1 for r in result.data if r["outcome"] == "loss")
    neutral = sum(1 for r in result.data if r["outcome"] == "neutral")

    return {
        "asset": asset,
        "total": total,
        "wins": wins,
        "losses": losses,
        "neutral": neutral,
        "win_rate": round(wins / (wins + losses), 3) if (wins + losses) > 0 else None,
    }
