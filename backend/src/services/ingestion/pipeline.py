"""Ingestion pipeline: fetch → deduplicate → chunk → index → report."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from src.models.schemas import IngestionFailure, IngestionReport
from src.services import logging as svc_logging
from src.services.ingestion.chunker import chunk_document
from src.services.ingestion.edgar_client import fetch_filings
from src.services.ingestion.indexer import index_chunks

_KNOWN_ACCESSIONS: set[str] = set()


async def _is_already_indexed(accession_number: str) -> bool:
    if accession_number in _KNOWN_ACCESSIONS:
        return True
    try:
        from elasticsearch import AsyncElasticsearch
        import os

        url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        async with AsyncElasticsearch([url]) as es:
            resp = await es.search(
                index="earnings_chunks",
                body={"query": {"term": {"accession_number": accession_number}}, "size": 1},
            )
            exists = resp["hits"]["total"]["value"] > 0
        if exists:
            _KNOWN_ACCESSIONS.add(accession_number)
        return exists
    except Exception:
        return False


async def run_ingestion(
    ticker: str,
    filing_types: list[str] | None = None,
    max_filings: int = 4,
    triggered_by: Literal["schedule", "api"] = "api",
    force: bool = False,
) -> IngestionReport:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    report = IngestionReport(
        run_id=run_id,
        ticker=ticker,
        triggered_by=triggered_by,
        started_at=started_at,
    )

    try:
        filing_docs = await fetch_filings(ticker, filing_types, max_filings)
    except Exception as exc:
        report.failures.append(
            IngestionFailure(
                source_url=f"EDGAR fetch for {ticker}",
                error_type="fetch_error",
                error_message=str(exc),
                occurred_at=datetime.now(timezone.utc),
            )
        )
        report.completed_at = datetime.now(timezone.utc)
        svc_logging.write_ingestion_report(report)
        return report

    for filing in filing_docs:
        if not force and await _is_already_indexed(filing.accession_number):
            report.filings_skipped += 1
            continue

        if not filing.text.strip():
            report.failures.append(
                IngestionFailure(
                    accession_number=filing.accession_number,
                    source_url=filing.source_url,
                    error_type="unsupported_format",
                    error_message="Document text is empty (possible image-only PDF)",
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            continue

        metadata = {
            "cik": filing.cik,
            "ticker": filing.ticker,
            "filing_type": filing.filing_type,
            "fiscal_period": filing.fiscal_period,
            "period_date": filing.period_date,
        }

        try:
            chunks = chunk_document(filing.text, filing.accession_number, metadata)
        except Exception as exc:
            report.failures.append(
                IngestionFailure(
                    accession_number=filing.accession_number,
                    source_url=filing.source_url,
                    error_type="chunking_error",
                    error_message=str(exc),
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            continue

        chunk_failures = await index_chunks(chunks)
        if chunk_failures:
            report.failures.extend(chunk_failures)
        else:
            report.filings_fetched += 1
            report.chunks_indexed += len(chunks)
            _KNOWN_ACCESSIONS.add(filing.accession_number)

    report.completed_at = datetime.now(timezone.utc)
    svc_logging.write_ingestion_report(report)
    return report
