# Data Model: Earnings Intelligence Platform

**Branch**: `001-earnings-intelligence-rag` | **Date**: 2026-03-22

---

## Entity: Filing

Represents a single regulatory document fetched from SEC EDGAR.

| Field | Type | Constraints |
|---|---|---|
| `accession_number` | `str` | Primary identifier. Format: `XXXXXXXXXX-YY-ZZZZZZ`. UNIQUE. |
| `cik` | `str` | SEC Central Index Key. Required. 10-digit zero-padded. |
| `ticker` | `str` | Exchange ticker symbol. Required. Uppercase. |
| `filing_type` | `Literal["10-K", "10-Q"]` | Required. |
| `fiscal_period` | `str` | Human-readable period label, e.g., `"Q3 2024"`. Required. |
| `period_date` | `date` | End date of the fiscal period (ISO 8601). Required. |
| `filed_date` | `date` | Date the filing was submitted to SEC EDGAR. Required. |
| `source_url` | `str` | EDGAR document URL used for fetch. Required. |
| `ingested_at` | `datetime` | UTC timestamp of when ingestion completed. Required. |
| `chunk_count` | `int` | Number of chunks produced from this filing. Required. ≥ 1. |

**Uniqueness rule**: `accession_number` is the deduplication key (FR-006).
A filing with a matching `accession_number` already in the index MUST NOT be re-indexed.

---

## Entity: Chunk

A text passage extracted from a Filing for dual indexing (vector + keyword).

| Field | Type | Constraints |
|---|---|---|
| `chunk_id` | `str` | Unique ID. Format: `{accession_number}_chunk_{index}`. |
| `accession_number` | `str` | Foreign key to Filing. Required. |
| `cik` | `str` | Denormalized from Filing for filter performance. Required. |
| `ticker` | `str` | Denormalized from Filing. Required. |
| `filing_type` | `str` | Denormalized from Filing. Required. |
| `fiscal_period` | `str` | Denormalized from Filing. Required. |
| `period_date` | `date` | Denormalized from Filing. Required. |
| `chunk_index` | `int` | Zero-based position within the parent filing. Required. ≥ 0. |
| `page_number` | `int` | Estimated page number derived from character offset. Required. ≥ 1. |
| `text` | `str` | Raw text content. Required. Max 512 tokens (tiktoken cl100k_base). |
| `token_count` | `int` | Actual token count. Required. 1–512. |

**Indexing**:
- Pinecone: `chunk_id` as vector ID; `text` embedding (1536 dims); metadata fields:
  `ticker`, `filing_type`, `fiscal_period`, `period_date`, `accession_number`, `page_number`.
- Elasticsearch `earnings_chunks` index: all fields; `text` with `english` analyzer;
  `ticker`, `filing_type`, `fiscal_period` as `keyword` for filtering.

---

## Entity: QueryRequest

Represents an analyst's inbound query.

| Field | Type | Constraints |
|---|---|---|
| `query_text` | `str` | Natural language question. Required. 1–2000 chars. |
| `fiscal_period_filter` | `str \| None` | Optional fiscal period restriction, e.g., `"Q3 2024"`. |
| `ticker_filter` | `list[str] \| None` | Optional list of tickers to restrict retrieval. |

---

## Entity: CompanyResult

A single company's financial data within a QueryResult.

| Field | Type | Constraints |
|---|---|---|
| `name` | `str` | Company name as it appears in the filing. Required. |
| `ticker` | `str` | Ticker symbol. Required. |
| `metric_name` | `str` | The financial metric being reported, e.g., `"gross_margin"`. Required. |
| `prior_value` | `float \| None` | Prior period value. `null` if not found in source. |
| `current_value` | `float \| None` | Current/guidance value. `null` if not found in source. |
| `change` | `float \| None` | Delta (current − prior). `null` if either value is absent. |
| `unit` | `str \| None` | Unit of measurement, e.g., `"ratio"`, `"USD_millions"`. |
| `cite` | `str` | Citation reference. Format: `{accession_number}_page_{page_number}`. Required. NEVER null. |

**Validation rule**: `cite` MUST always be present (FR-004). If the LLM cannot
identify a source chunk, the company entry MUST be omitted entirely — not returned
with a null cite.

---

## Entity: QueryResult

The full structured response to an analyst query.

| Field | Type | Constraints |
|---|---|---|
| `query_text` | `str` | Echo of the original query. Required. |
| `companies` | `list[CompanyResult]` | 0–20 entries. Empty list if no evidence found. |
| `truncated` | `bool` | `true` if result set was capped at 20. Required. |
| `explanation` | `str \| None` | Human-readable note if no results found or results are partial. |
| `generated_at` | `datetime` | UTC timestamp of response generation. Required. |
| `cache_hit` | `bool` | Whether response was served from cache. Required. |

---

## Entity: IngestionReport

Summary artifact returned after an ingestion run (scheduled or on-demand).

| Field | Type | Constraints |
|---|---|---|
| `run_id` | `str` | UUID. Unique per run. Required. |
| `ticker` | `str \| None` | Ticker if on-demand; `null` if scheduled full-corpus run. |
| `triggered_by` | `Literal["schedule", "api"]` | Trigger type. Required. |
| `started_at` | `datetime` | UTC. Required. |
| `completed_at` | `datetime \| None` | UTC. `null` if run is still in progress. |
| `filings_fetched` | `int` | Number of filings successfully fetched. Required. ≥ 0. |
| `chunks_indexed` | `int` | Total chunks written to both indexes. Required. ≥ 0. |
| `filings_skipped` | `int` | Count of filings skipped due to deduplication. Required. ≥ 0. |
| `failures` | `list[IngestionFailure]` | Per-document failures. Empty list if none. |

---

## Entity: IngestionFailure

A record of a single document that failed during an ingestion run.

| Field | Type | Constraints |
|---|---|---|
| `accession_number` | `str \| None` | Known if failure occurs post-fetch; `null` if fetch itself failed. |
| `source_url` | `str` | The URL that was attempted. Required. |
| `error_type` | `str` | Short error category, e.g., `"network_error"`, `"unsupported_format"`. Required. |
| `error_message` | `str` | Human-readable failure detail. Required. |
| `occurred_at` | `datetime` | UTC timestamp. Required. |

---

## Entity: QueryLog

Audit record written for every query execution (FR-007). Written to persistent log
storage; not returned to the caller.

| Field | Type | Constraints |
|---|---|---|
| `log_id` | `str` | UUID. Required. |
| `query_text` | `str` | Full query text. Required. |
| `fiscal_period_filter` | `str \| None` | Applied filter if any. |
| `ticker_filter` | `list[str] \| None` | Applied filter if any. |
| `cache_hit` | `bool` | Required. |
| `pinecone_scores` | `list[float]` | Top-N dense retrieval scores. Required if not cache hit. |
| `es_scores` | `list[float]` | Top-N BM25 scores. Required if not cache hit. |
| `reranker_scores` | `list[float]` | Cohere reranker scores for top-10. Required if not cache hit. |
| `model_used` | `str` | LLM model identifier, e.g., `"gpt-4-turbo-2024-04-09"`. Required. |
| `latency_ms` | `int` | End-to-end latency in milliseconds. Required. |
| `citations_returned` | `list[str]` | All `cite` values in the response. Required. |
| `result_count` | `int` | Number of CompanyResult entries returned. Required. |
| `logged_at` | `datetime` | UTC. Required. |
| `retention_until` | `date` | Must be ≥ 90 days from `logged_at` (SC-006). Required. |

---

## State Transitions

### Ingestion Run Lifecycle

```
PENDING → IN_PROGRESS → COMPLETED
                      → FAILED (partial: some docs indexed, some failed)
```

### Filing Lifecycle

```
NOT_INDEXED → INDEXED (after successful chunk embedding + dual index write)
INDEXED    → INDEXED (re-ingestion attempt → deduplicated, no state change)
```

---

## Validation Rules Summary

- `CompanyResult.cite` MUST never be null or omitted if the entry is present.
- `QueryResult.companies` length MUST NOT exceed 20.
- `Chunk.token_count` MUST NOT exceed 512.
- `Filing.accession_number` MUST be unique across the index at ingestion time.
- `QueryLog.retention_until` MUST be at least 90 days after `logged_at`.
- PII MUST NOT appear in any field of Chunk, CompanyResult, or QueryLog.
