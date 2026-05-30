"""Structured JSON logger for query and ingestion audit records."""
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone

from src.models.schemas import IngestionReport, QueryLog

_logger = logging.getLogger("fintelligence")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(obj: object) -> object:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def write_query_log(log: QueryLog) -> None:
    min_retention = log.logged_at.date() + timedelta(days=90)
    assert log.retention_until >= min_retention, (
        f"retention_until {log.retention_until} is before minimum {min_retention}"
    )
    entry = json.dumps({"type": "query_log", **log.model_dump()}, default=_serialize)
    _logger.info(entry)

    import os
    log_path = os.path.join(os.getcwd(), "logs", "query_audit.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def write_ingestion_report(report: IngestionReport) -> None:
    _logger.info(
        json.dumps({"type": "ingestion_report", **report.model_dump()}, default=_serialize)
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"fintelligence.{name}")
