"""Build and persist QueryLog records for every query execution."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from src.models.schemas import QueryLog, QueryRequest, QueryResult
from src.services import logging as svc_logging


def write_query_log(
    query_request: QueryRequest,
    result: QueryResult,
    pinecone_scores: list[float],
    es_scores: list[float],
    reranker_scores: list[float],
    latency_ms: int,
) -> None:
    now = datetime.now(timezone.utc)
    log = QueryLog(
        log_id=str(uuid.uuid4()),
        query_text=query_request.query_text,
        fiscal_period_filter=query_request.fiscal_period_filter,
        ticker_filter=query_request.ticker_filter,
        cache_hit=result.cache_hit,
        pinecone_scores=pinecone_scores,
        es_scores=es_scores,
        reranker_scores=reranker_scores,
        model_used="gpt-4-turbo-2024-04-09",
        latency_ms=latency_ms,
        citations_returned=[c.cite for c in result.companies],
        result_count=len(result.companies),
        logged_at=now,
        retention_until=now.date() + timedelta(days=90),
    )
    svc_logging.write_query_log(log)
