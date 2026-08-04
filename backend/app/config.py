"""Optional in-process scheduler.

IMPORTANT — read this before relying on it: Render's free web service tier
spins down after 15 minutes with no incoming HTTP request. A sleeping
process fires no cron jobs at all, in-process or otherwise. So the
*reliable* trigger for scheduled refreshes is the GitHub Actions workflow
in .github/workflows/scheduled-refresh.yml, which calls each /*/refresh
endpoint over HTTP in dependency order — that same traffic is also what
wakes the service back up and keeps Supabase from pausing.

This in-process scheduler is kept as a defense-in-depth layer for whenever
the service happens to already be awake, so data still refreshes without
waiting for the next GitHub Actions tick. Do not depend on it alone.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services import (
    ai_decision_service,
    big_picture_service,
    dxy_service,
    history_service,
    ict_service,
    intermediate_service,
    market_data_service,
    news_service,
    notifications_service,
    performance_service,
    rates_service,
    short_term_service,
    treasury_service,
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def run_full_refresh_chain() -> None:
    """Runs every module in dependency order: raw data first (including
    the shared market_prices bars everything else in this list reads
    from), then the three Top-Down Analysis perspectives, then AI Decision
    (which reads all of it), then Historical Learning (grades old
    decisions), then Performance and Notifications (read the results of
    both)."""
    steps = [
        ("treasury", treasury_service.refresh_treasury_data),
        ("rates", rates_service.refresh_rates_data),
        ("dxy", dxy_service.refresh_dxy_data),
        ("news", news_service.refresh_news_data),
        ("market_data", market_data_service.refresh_market_prices),
        ("ict", ict_service.refresh_ict_signals),
        ("ict_reinforcement_learning", ict_service.evaluate_learning_records),
        ("cpi", big_picture_service.refresh_cpi_data),
        ("commodity_index", big_picture_service.refresh_commodity_index),
        ("macro_regime", big_picture_service.compute_macro_regime),
        ("seasonality", big_picture_service.refresh_seasonality),
        ("topdown_bias", intermediate_service.refresh_topdown_bias),
        ("cot", intermediate_service.refresh_cot_data),
        ("correlations", short_term_service.compute_correlations),
        ("ipda_ranges", short_term_service.refresh_ipda_ranges),
        ("ai_decision", ai_decision_service.refresh_ai_decisions),
        ("history", history_service.evaluate_pending_decisions),
        ("performance", performance_service.refresh_performance_metrics),
        ("notifications", notifications_service.refresh_notifications),
    ]
    for name, fn in steps:
        try:
            await fn()
        except Exception:  # noqa: BLE001 — one module failing shouldn't block the rest
            logger.exception("Scheduled refresh step '%s' failed", name)


def start_scheduler() -> None:
    scheduler.add_job(
        run_full_refresh_chain,
        CronTrigger(hour="1,13,19", minute=0),
        id="run_full_refresh_chain",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
