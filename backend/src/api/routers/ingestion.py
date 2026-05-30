"""Ingestion API endpoints: POST /ingest, GET /ingest/{run_id}, GET /ingest/schedule."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.models.schemas import IngestionReport

router = APIRouter(tags=["ingestion"])

_active_runs: dict[str, IngestionReport] = {}


class IngestRequest(BaseModel):
    ticker: str
    filing_types: list[str] = Field(default=["10-K", "10-Q"])
    max_filings: int = Field(default=4, ge=1, le=20)


async def _run_ingestion_background(run_id: str, request: IngestRequest) -> None:
    from src.services.ingestion.pipeline import run_ingestion

    try:
        report = await run_ingestion(
            ticker=request.ticker,
            filing_types=request.filing_types,
            max_filings=request.max_filings,
            triggered_by="api",
        )
        _active_runs[run_id] = report
    except Exception as exc:
        existing = _active_runs.get(run_id)
        if existing:
            existing.completed_at = datetime.now(timezone.utc)
        from src.services import logging as svc_logging
        svc_logging.get_logger("ingestion_api").error(f"Ingestion run {run_id} failed: {exc}")


@router.post("/ingest", status_code=202)
async def trigger_ingest(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    initial_report = IngestionReport(
        run_id=run_id,
        ticker=request.ticker,
        triggered_by="api",
        started_at=started_at,
    )
    _active_runs[run_id] = initial_report

    background_tasks.add_task(_run_ingestion_background, run_id, request)

    return {
        "run_id": run_id,
        "ticker": request.ticker,
        "triggered_by": "api",
        "started_at": started_at.isoformat(),
        "status": "in_progress",
    }


@router.get("/ingest/schedule")
async def get_schedule() -> dict[str, Any]:
    from src.scheduler.ingestion_job import get_scheduler
    import os

    scheduler = get_scheduler()
    cron_expr = os.environ.get("INGESTION_CRON", "0 6 * * 1")
    next_run = None
    last_run_id = None

    if scheduler:
        job = scheduler.get_job("scheduled_ingestion")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    return {
        "enabled": scheduler is not None and scheduler.running,
        "cron_expression": cron_expr,
        "description": "Every Monday at 06:00 UTC",
        "next_run_at": next_run,
        "last_run_id": last_run_id,
        "last_run_completed_at": None,
    }


@router.get("/ingest/{run_id}")
async def get_ingest_status(run_id: str) -> IngestionReport | JSONResponse:
    report = _active_runs.get(run_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": "not_found", "run_id": run_id})
    return report
