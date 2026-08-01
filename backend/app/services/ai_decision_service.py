"""AI Decision Engine.

This is a rules-based multi-factor scoring model — a systematic weighting
of signals already computed by the other engines — not a machine-learning
model and not an LLM call. That is a deliberate choice, not a shortcut:
- It costs nothing to run (no inference API), matching the project's
  free-tier-first requirement.
- Every input and weight is inspectable — the rationale generator lists
  exactly which factors fired and why, which a black-box model can't do
  without extra tooling anyway.
An optional enhancement layer is documented at the bottom of this file:
sending the same factor summary to an LLM (e.g. the Anthropic API) for a
more natural-language rationale. That needs your own paid API key, so it's
opt-in rather than built into the default path.

Signals consulted (each pulled from tables the other engines already
populate — no new external calls here):
  - Treasury:  10Y-2Y curve inversion
  - Rates:     2Y-vs-funds-rate expectation (cuts / hikes / steady)
  - DXY:       OLS trend direction
  - ICT:       most recent signal's direction, per asset
  - News:      sentiment balance of recent headlines

This produces decision-support output, not investment advice — the
dashboard's footer disclaimer applies here specifically.
"""
from collections import Counter
from datetime import datetime, timezone

from app.database import get_supabase

# weight, and which trend/direction counts as "bullish" for that asset
FACTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "XAUUSD": {"curve_inversion": 1.0, "rate_expectation": 1.0, "dxy_trend": 1.0, "ict_signal": 0.5, "news_sentiment": 0.5},
    "NQ": {"curve_inversion": 1.0, "rate_expectation": 1.0, "dxy_trend": 0.25, "ict_signal": 0.5, "news_sentiment": 0.5},
}

NEUTRAL_BAND = 0.5  # |score| below this -> "neutral"


async def _get_curve_inversion(supabase) -> bool | None:
    result = (
        supabase.table("treasury_yields")
        .select("series, date, value")
        .in_("series", ["10Y", "2Y"])
        .order("date", desc=True)
        .limit(10)
        .execute()
    )
    latest: dict[str, float] = {}
    for row in result.data:
        if row["series"] not in latest:
            latest[row["series"]] = row["value"]
    if "10Y" in latest and "2Y" in latest:
        return latest["10Y"] - latest["2Y"] < 0
    return None


async def _get_rate_expectation(supabase) -> str | None:
    # Reuse the same 2Y-vs-funds-rate comparison the Rates engine already
    # computes, rather than importing that whole service — one query here
    # keeps this module independent of the Rates engine's internals.
    result = (
        supabase.table("interest_rates")
        .select("series, date, value")
        .eq("series", "FEDFUNDS")
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    funds_rate = result.data[0]["value"]

    two_year = (
        supabase.table("treasury_yields")
        .select("value")
        .eq("series", "2Y")
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if not two_year.data:
        return None
    diff = two_year.data[0]["value"] - funds_rate
    if diff <= -0.25:
        return "cuts_expected"
    if diff >= 0.25:
        return "hikes_expected"
    return "steady"


async def _get_dxy_trend(supabase) -> str | None:
    result = (
        supabase.table("dxy_forecasts").select("trend").order("created_at", desc=True).limit(1).execute()
    )
    return result.data[0]["trend"] if result.data else None


async def _get_ict_direction(supabase, asset: str) -> str | None:
    result = (
        supabase.table("ict_signals")
        .select("direction")
        .eq("asset", asset)
        .order("detected_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0]["direction"] if result.data else None


async def _get_news_sentiment(supabase, asset: str) -> str | None:
    result = (
        supabase.table("economic_news")
        .select("sentiment, related_asset")
        .in_("related_asset", [asset, "both"])
        .order("published_at", desc=True)
        .limit(20)
        .execute()
    )
    if not result.data:
        return None
    counts = Counter(row["sentiment"] for row in result.data)
    if counts["positive"] > counts["negative"]:
        return "positive"
    if counts["negative"] > counts["positive"]:
        return "negative"
    return "neutral"


def _factor_contribution(asset: str, factor: str, value) -> tuple[float, str]:
    """Returns (signed weighted contribution, human-readable note). Signs
    are asset-specific: e.g. a curve inversion is bullish for Gold but
    bearish for Nasdaq — see the module docstring for the reasoning."""
    weight = FACTOR_WEIGHTS[asset][factor]
    gold = asset == "XAUUSD"

    if factor == "curve_inversion":
        if value is None:
            return 0.0, "Curve inversion: no data"
        bullish_for_gold = value is True
        sign = (1 if bullish_for_gold else -1) if gold else (-1 if bullish_for_gold else 1)
        return sign * weight, f"Curve {'inverted' if value else 'not inverted'}"

    if factor == "rate_expectation":
        if value is None:
            return 0.0, "Rate expectation: no data"
        if value == "steady":
            return 0.0, "Rate expectation: steady"
        cuts = value == "cuts_expected"
        sign = 1 if cuts else -1  # cuts are bullish gold AND bullish equities
        return sign * weight, f"Rate expectation: {value}"

    if factor == "dxy_trend":
        if value in (None, "flat"):
            return 0.0, "DXY trend: flat or no data"
        weaker_dollar = value == "down"
        sign = 1 if weaker_dollar else -1  # weaker dollar: bullish gold, mildly bullish Nasdaq earnings
        return sign * weight, f"DXY trend: {value}"

    if factor == "ict_signal":
        if value is None:
            return 0.0, "ICT signal: no data"
        sign = 1 if value == "bullish" else -1
        return sign * weight, f"Latest ICT signal: {value}"

    if factor == "news_sentiment":
        if value in (None, "neutral"):
            return 0.0, "News sentiment: neutral or no data"
        sign = 1 if value == "positive" else -1
        return sign * weight, f"News sentiment: {value}"

    return 0.0, f"Unknown factor: {factor}"


async def compute_decision(asset: str) -> dict:
    if asset not in FACTOR_WEIGHTS:
        raise ValueError(f"Unknown asset '{asset}'. Valid: {sorted(FACTOR_WEIGHTS)}")

    supabase = get_supabase()

    raw_values = {
        "curve_inversion": await _get_curve_inversion(supabase),
        "rate_expectation": await _get_rate_expectation(supabase),
        "dxy_trend": await _get_dxy_trend(supabase),
        "ict_signal": await _get_ict_direction(supabase, asset),
        "news_sentiment": await _get_news_sentiment(supabase, asset),
    }

    contributions = {
        factor: _factor_contribution(asset, factor, value) for factor, value in raw_values.items()
    }
    total_score = sum(c[0] for c in contributions.values())
    max_score = sum(FACTOR_WEIGHTS[asset].values())

    if total_score > NEUTRAL_BAND:
        decision = "long"
    elif total_score < -NEUTRAL_BAND:
        decision = "short"
    else:
        decision = "neutral"

    confidence = round(min(1.0, abs(total_score) / max_score), 3) if max_score else 0.0
    rationale = "; ".join(note for _, note in contributions.values())

    return {
        "asset": asset,
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "contributing_factors": {k: raw_values[k] for k in raw_values},
    }


async def refresh_ai_decisions() -> dict:
    supabase = get_supabase()
    decisions = []
    for asset in FACTOR_WEIGHTS:
        decision = await compute_decision(asset)
        decisions.append(decision)
        supabase.table("ai_decisions").insert(
            {**decision, "outcome_evaluated": False}
        ).execute()
    return {"decisions_created": len(decisions)}


async def get_latest_decision(asset: str) -> dict | None:
    if asset not in FACTOR_WEIGHTS:
        raise ValueError(f"Unknown asset '{asset}'. Valid: {sorted(FACTOR_WEIGHTS)}")

    supabase = get_supabase()
    result = (
        supabase.table("ai_decisions")
        .select("*")
        .eq("asset", asset)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


# ---------------------------------------------------------------------------
# Optional enhancement (not wired up by default — needs your own paid key):
#
# async def generate_llm_rationale(decision: dict) -> str:
#     """POST decision['contributing_factors'] to api.anthropic.com/v1/messages
#     asking for a 2-3 sentence plain-English rationale. Costs a fraction of a
#     cent per call at Haiku pricing and only needs to run once per decision
#     (a few times a day), so it's cheap even though it isn't free. Left
#     unimplemented here deliberately — wire it in only if you're comfortable
#     adding ANTHROPIC_API_KEY as the one paid dependency in this stack."""
