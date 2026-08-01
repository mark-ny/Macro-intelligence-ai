"""Economic News Intelligence Engine.

Two free data sources, combined:
  1. Currents API (currentsapi.services) — real headlines. Free tier: 1,000
     requests/day, no card required, CORS-enabled. https://currentsapi.services
  2. FRED's release calendar — official dates for high-impact US data
     releases (CPI, the jobs report, GDP, ...). More useful to a macro/ICT
     trader than generic headlines, and it's not something NewsAPI-style
     services provide at all.

Sentiment is a disclosed keyword heuristic, not NLP: it counts hits from a
small positive/negative macro lexicon. It is a real, inspectable technique
— just not a sophisticated one. Treat the "sentiment" field as a rough
signal, not ground truth.
"""
from datetime import datetime, timedelta, timezone

import httpx

from app.cache import ttl_cache
from app.config import get_settings
from app.database import get_supabase

CURRENTS_SEARCH_URL = "https://api.currentsapi.services/v1/search"
FRED_RELEASES_URL = "https://api.stlouisfed.org/fred/releases"
FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"

# Keywords chosen for relevance to Gold (XAU/USD) and Nasdaq (NQ), not
# general news — this is a macro/rates/dollar feed, not a headline firehose.
SEARCH_KEYWORDS = [
    "Federal Reserve",
    "inflation",
    "interest rates",
    "jobs report",
    "gold price",
    "Nasdaq",
    "recession",
]

# FRED release names we care about for the calendar. Matched by substring
# against /fred/releases rather than hardcoding numeric release_ids, which
# are easy to get wrong and silently return the wrong release.
CALENDAR_RELEASE_NAMES = [
    "Employment Situation",
    "Consumer Price Index",
    "Gross Domestic Product",
    "Personal Income and Outlays",
    "Producer Price Index",
]

POSITIVE_TERMS = [
    "beat expectations", "better than expected", "rate cut", "cooling inflation",
    "strong jobs", "expansion", "rally", "growth accelerat", "eases", "easing",
]
NEGATIVE_TERMS = [
    "miss expectations", "worse than expected", "rate hike", "inflation surge",
    "layoffs", "contraction", "recession", "slump", "stagflation", "sell-off",
]


def _score_sentiment(text: str) -> str:
    lowered = text.lower()
    positive = sum(term in lowered for term in POSITIVE_TERMS)
    negative = sum(term in lowered for term in NEGATIVE_TERMS)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def _guess_related_asset(text: str) -> str:
    lowered = text.lower()
    gold_hit = any(term in lowered for term in ["gold", "xau"])
    nasdaq_hit = any(term in lowered for term in ["nasdaq", "tech stock", "equities"])
    if gold_hit and nasdaq_hit:
        return "both"
    if gold_hit:
        return "XAUUSD"
    if nasdaq_hit:
        return "NQ"
    return "both"  # macro news (Fed, inflation, jobs) affects both by default


async def _fetch_headlines_for_keyword(client: httpx.AsyncClient, keyword: str, api_key: str) -> list[dict]:
    response = await client.get(
        CURRENTS_SEARCH_URL,
        params={"keywords": keyword, "language": "en", "page_size": 10, "apiKey": api_key},
    )
    response.raise_for_status()
    return response.json().get("news", [])


async def refresh_news_headlines() -> dict:
    settings = get_settings()
    if not settings.currents_api_key:
        raise RuntimeError("CURRENTS_API_KEY is not set — see README > Local development.")

    supabase = get_supabase()
    rows: list[dict] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for keyword in SEARCH_KEYWORDS:
            try:
                articles = await _fetch_headlines_for_keyword(client, keyword, settings.currents_api_key)
            except Exception:  # noqa: BLE001 — one bad keyword shouldn't sink the whole refresh
                continue

            for article in articles:
                url = article.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                headline = article.get("title", "")
                summary = article.get("description")
                combined_text = f"{headline} {summary or ''}"

                rows.append({
                    "published_at": article.get("published"),
                    "source": article.get("author") or "Currents",
                    "headline": headline,
                    "summary": summary,
                    "sentiment": _score_sentiment(combined_text),
                    "impact_level": "medium",
                    "related_asset": _guess_related_asset(combined_text),
                    "url": url,
                })

    if rows:
        supabase.table("economic_news").upsert(rows, on_conflict="url").execute()

    return {"headlines_upserted": len(rows)}


async def _resolve_release_ids(client: httpx.AsyncClient, api_key: str, names: list[str]) -> dict[str, int]:
    response = await client.get(
        FRED_RELEASES_URL, params={"api_key": api_key, "file_type": "json", "limit": 1000}
    )
    response.raise_for_status()
    all_releases = response.json().get("releases", [])

    resolved: dict[str, int] = {}
    for name in names:
        match = next((r for r in all_releases if name.lower() in r["name"].lower()), None)
        if match:
            resolved[name] = match["id"]
    return resolved


async def refresh_economic_calendar(days_ahead: int = 60) -> dict:
    settings = get_settings()
    if not settings.fred_api_key:
        raise RuntimeError("FRED_API_KEY is not set — see README > Local development.")

    supabase = get_supabase()
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)
    rows: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        release_ids = await _resolve_release_ids(client, settings.fred_api_key, CALENDAR_RELEASE_NAMES)

        for name, release_id in release_ids.items():
            response = await client.get(
                FRED_RELEASE_DATES_URL,
                params={
                    "release_id": release_id,
                    "api_key": settings.fred_api_key,
                    "file_type": "json",
                    "include_release_dates_with_no_data": "true",
                },
            )
            response.raise_for_status()
            for entry in response.json().get("release_dates", []):
                release_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                if today <= release_date <= horizon:
                    rows.append({
                        "release_name": name,
                        "release_id": release_id,
                        "scheduled_at": entry["date"],
                        "importance": "high",
                    })

    if rows:
        supabase.table("economic_calendar").upsert(
            rows, on_conflict="release_id,scheduled_at"
        ).execute()

    return {"calendar_events_upserted": len(rows)}


async def refresh_news_data() -> dict:
    """Combined refresh — called by the scheduler and by POST /api/news/refresh."""
    headlines_result = await refresh_news_headlines()
    calendar_result = await refresh_economic_calendar()
    return {**headlines_result, **calendar_result}


@ttl_cache(seconds=600)
async def get_headlines(limit: int = 15) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("economic_news")
        .select("*")
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@ttl_cache(seconds=600)
async def get_upcoming_calendar(days_ahead: int = 14) -> list[dict]:
    supabase = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    horizon = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    result = (
        supabase.table("economic_calendar")
        .select("release_name, scheduled_at, importance")
        .gte("scheduled_at", today)
        .lte("scheduled_at", horizon)
        .order("scheduled_at")
        .execute()
    )
    return result.data
