from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Filing(BaseModel):
    accession_number: str = Field(..., pattern=r"^\d{10}-\d{2}-\d{6}$")
    cik: str = Field(..., pattern=r"^\d{10}$")
    ticker: str
    filing_type: Literal["10-K", "10-Q"]
    fiscal_period: str
    period_date: date
    filed_date: date
    source_url: str
    ingested_at: datetime
    chunk_count: int = Field(..., ge=1)

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.upper()


class Chunk(BaseModel):
    chunk_id: str
    accession_number: str
    cik: str
    ticker: str
    filing_type: str
    fiscal_period: str
    period_date: date
    chunk_index: int = Field(..., ge=0)
    page_number: int = Field(..., ge=1)
    text: str
    token_count: int = Field(..., ge=1, le=512)

    @model_validator(mode="after")
    def validate_chunk_id_format(self) -> "Chunk":
        expected = f"{self.accession_number}_chunk_{self.chunk_index}"
        if self.chunk_id != expected:
            raise ValueError(
                f"chunk_id must be '{expected}', got '{self.chunk_id}'"
            )
        return self


class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=2000)
    fiscal_period_filter: str | None = None
    ticker_filter: list[str] | None = Field(None, max_length=50)

    @field_validator("ticker_filter")
    @classmethod
    def tickers_uppercase(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [t.upper() for t in v]
        return v


class CompanyResult(BaseModel):
    name: str
    ticker: str
    metric_name: str
    prior_value: float | None = None
    current_value: float | None = None
    change: float | None = None
    unit: str | None = None
    cite: str = Field(..., pattern=r"^.+_page_\d+$")

    @model_validator(mode="after")
    def validate_change(self) -> "CompanyResult":
        if self.prior_value is not None and self.current_value is not None:
            expected = round(self.current_value - self.prior_value, 10)
            if self.change is None:
                self.change = expected
        return self


class QueryResult(BaseModel):
    query_text: str
    companies: list[CompanyResult] = Field(default_factory=list, max_length=20)
    truncated: bool
    explanation: str | None = None
    generated_at: datetime
    cache_hit: bool

    @field_validator("companies")
    @classmethod
    def max_twenty_companies(cls, v: list[CompanyResult]) -> list[CompanyResult]:
        if len(v) > 20:
            raise ValueError("companies list must not exceed 20 entries")
        return v


class IngestionFailure(BaseModel):
    accession_number: str | None = None
    source_url: str
    error_type: str
    error_message: str
    occurred_at: datetime


class IngestionReport(BaseModel):
    run_id: str
    ticker: str | None = None
    triggered_by: Literal["schedule", "api"]
    started_at: datetime
    completed_at: datetime | None = None
    filings_fetched: int = Field(default=0, ge=0)
    chunks_indexed: int = Field(default=0, ge=0)
    filings_skipped: int = Field(default=0, ge=0)
    failures: list[IngestionFailure] = Field(default_factory=list)


class QueryLog(BaseModel):
    log_id: str
    query_text: str
    fiscal_period_filter: str | None = None
    ticker_filter: list[str] | None = None
    cache_hit: bool
    pinecone_scores: list[float] = Field(default_factory=list)
    es_scores: list[float] = Field(default_factory=list)
    reranker_scores: list[float] = Field(default_factory=list)
    model_used: str
    latency_ms: int
    citations_returned: list[str] = Field(default_factory=list)
    result_count: int
    logged_at: datetime
    retention_until: date

    @model_validator(mode="after")
    def validate_retention(self) -> "QueryLog":
        from datetime import timedelta

        min_retention = self.logged_at.date() + timedelta(days=90)
        if self.retention_until < min_retention:
            raise ValueError(
                f"retention_until must be >= {min_retention} (90 days from logged_at)"
            )
        return self
