"""APScheduler cron job for scheduled ingestion runs."""
from __future__ import annotations

import asyncio
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler: AsyncIOScheduler | None = None
_WATCHLIST = ["NVDA", "AMD", "INTC", "MSFT", "GOOGL"]


async def _run_scheduled_ingestion() -> None:
    from src.services.ingestion.pipeline import run_ingestion

    for ticker in _WATCHLIST:
        try:
            report = await run_ingestion(ticker, triggered_by="schedule")
            from src.services import logging as svc_logging
            svc_logging.write_ingestion_report(report)
        except Exception as exc:
            from src.services import logging as svc_logging
            svc_logging.get_logger("scheduler").error(
                f"Scheduled ingestion failed for {ticker}: {exc}"
            )


async def start_scheduler() -> None:
    global _scheduler
    cron_expr = os.environ.get("INGESTION_CRON", "0 6 * * 1")
    parts = cron_expr.split()

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_scheduled_ingestion,
        trigger=CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        ),
        id="scheduled_ingestion",
        name="Scheduled SEC EDGAR ingestion",
        replace_existing=True,
    )
    _scheduler.start()


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
