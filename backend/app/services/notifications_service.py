"""Notifications — generation side only.

This module *creates* notification rows using the service-role key, which
is the right tool for a scheduled job writing on behalf of every user.
Listing notifications and marking them read is deliberately NOT routed
through the backend: those are per-user reads/writes already protected by
the RLS policies in the migration (`auth.uid() = user_id`), so the
frontend does them directly against Supabase with the user's own session
(see frontend/src/app/notifications/page.tsx). Proxying reads through a
service-role backend client would either leak every user's notifications
or require re-implementing JWT verification here — RLS already solves it
correctly, so we use it.

Each check below is deduped against the last 24h so a scheduler running
hourly doesn't spam the same event repeatedly.
"""
from datetime import datetime, timedelta, timezone

from app.database import get_supabase


def _get_all_user_ids(supabase) -> list[str]:
    try:
        response = supabase.auth.admin.list_users()
    except Exception:  # noqa: BLE001 — no users yet, or admin API unavailable
        return []
    users = getattr(response, "users", response)
    return [u.id for u in users]


def _filter_by_pref(supabase, user_ids: list[str], pref_key: str) -> list[str]:
    """Drops users who've opted out of this notification category via
    Settings (user_settings.notification_prefs, wired up in
    frontend/src/app/settings/page.tsx). No settings row, or no explicit
    False for this key, means still enabled — opt-out, not opt-in, so
    existing users keep getting notifications after this was added."""
    if not user_ids:
        return []
    result = (
        supabase.table("user_settings")
        .select("user_id, notification_prefs")
        .in_("user_id", user_ids)
        .execute()
    )
    opted_out = {
        row["user_id"] for row in result.data if (row.get("notification_prefs") or {}).get(pref_key) is False
    }
    return [uid for uid in user_ids if uid not in opted_out]


def _already_notified_recently(supabase, notif_type: str, hours: int = 24) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    result = (
        supabase.table("notifications")
        .select("id")
        .eq("type", notif_type)
        .gte("created_at", cutoff)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _broadcast(supabase, user_ids: list[str], notif_type: str, title: str, body: str) -> int:
    if not user_ids:
        return 0
    rows = [{"user_id": uid, "type": notif_type, "title": title, "body": body} for uid in user_ids]
    supabase.table("notifications").insert(rows).execute()
    return len(rows)


async def check_curve_inversion(supabase, user_ids: list[str]) -> int:
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
    if "10Y" not in latest or "2Y" not in latest:
        return 0
    if latest["10Y"] - latest["2Y"] >= 0:
        return 0
    if _already_notified_recently(supabase, "curve_inversion"):
        return 0

    return _broadcast(
        supabase, user_ids, "curve_inversion", "Yield curve inverted",
        "The 10Y-2Y Treasury spread just turned negative.",
    )


async def check_ai_decision_changes(supabase, user_ids: list[str]) -> int:
    created = 0
    for asset in ("XAUUSD", "NQ"):
        result = (
            supabase.table("ai_decisions")
            .select("decision, created_at")
            .eq("asset", asset)
            .order("created_at", desc=True)
            .limit(2)
            .execute()
        )
        if len(result.data) < 2:
            continue
        latest, previous = result.data[0], result.data[1]
        if latest["decision"] == previous["decision"]:
            continue
        if _already_notified_recently(supabase, f"ai_decision_change_{asset}", hours=1):
            continue
        created += _broadcast(
            supabase, user_ids, f"ai_decision_change_{asset}",
            f"AI decision changed for {asset}",
            f"Moved from {previous['decision']} to {latest['decision']}.",
        )
    return created


async def check_upcoming_calendar_events(supabase, user_ids: list[str]) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    result = (
        supabase.table("economic_calendar")
        .select("release_name, scheduled_at")
        .in_("scheduled_at", [today, tomorrow])
        .eq("importance", "high")
        .execute()
    )
    created = 0
    for event in result.data:
        notif_type = f"calendar_{event['release_name']}_{event['scheduled_at']}"
        if _already_notified_recently(supabase, notif_type, hours=24):
            continue
        created += _broadcast(
            supabase, user_ids, notif_type, f"{event['release_name']} coming up",
            f"Scheduled for {event['scheduled_at']}.",
        )
    return created


async def refresh_notifications() -> dict:
    supabase = get_supabase()
    all_user_ids = _get_all_user_ids(supabase)

    return {
        "curve_inversion": await check_curve_inversion(
            supabase, _filter_by_pref(supabase, all_user_ids, "curve_inversion")
        ),
        "ai_decision_changes": await check_ai_decision_changes(
            supabase, _filter_by_pref(supabase, all_user_ids, "ai_decision_changes")
        ),
        "calendar_events": await check_upcoming_calendar_events(
            supabase, _filter_by_pref(supabase, all_user_ids, "calendar_events")
        ),
    }
