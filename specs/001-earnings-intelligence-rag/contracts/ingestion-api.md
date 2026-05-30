# Contract: Ingestion API

**Branch**: `001-earnings-intelligence-rag` | **Date**: 2026-03-22
**Base URL**: `/api/v1`

---

## POST /api/v1/ingest

Trigger on-demand ingestion of SEC filings for a specific ticker. Returns
immediately with a `run_id`; poll `GET /api/v1/ingest/{run_id}` for status.

### Request

```json
{
  "ticker": "NVDA",
  "filing_types": ["10-K", "10-Q"],
  "max_filings": 4
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `ticker` | `string` | Yes | Uppercase ticker symbol |
| `filing_types` | `array[string]` | No | Default: `["10-K", "10-Q"]` |
| `max_filings` | `integer` | No | Default: 4 (most recent per type). Max: 20. |

### Response — 202 Accepted

```json
{
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "ticker": "NVDA",
  "triggered_by": "api",
  "started_at": "2026-03-22T10:00:00Z",
  "status": "in_progress"
}
```

---

## GET /api/v1/ingest/{run_id}

Retrieve the status and result of an ingestion run.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `run_id` | `string` (UUID) | The run ID returned by POST /ingest |

### Response — 200 OK (completed)

```json
{
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "ticker": "NVDA",
  "triggered_by": "api",
  "started_at": "2026-03-22T10:00:00Z",
  "completed_at": "2026-03-22T10:02:34Z",
  "filings_fetched": 4,
  "chunks_indexed": 1842,
  "filings_skipped": 1,
  "failures": []
}
```

### Response — 200 OK (in progress)

```json
{
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "ticker": "NVDA",
  "triggered_by": "api",
  "started_at": "2026-03-22T10:00:00Z",
  "completed_at": null,
  "filings_fetched": 2,
  "chunks_indexed": 921,
  "filings_skipped": 0,
  "failures": []
}
```

### Response — 200 OK (with failures)

```json
{
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "ticker": "NVDA",
  "triggered_by": "api",
  "started_at": "2026-03-22T10:00:00Z",
  "completed_at": "2026-03-22T10:02:50Z",
  "filings_fetched": 3,
  "chunks_indexed": 1381,
  "filings_skipped": 0,
  "failures": [
    {
      "accession_number": null,
      "source_url": "https://www.sec.gov/Archives/...",
      "error_type": "network_error",
      "error_message": "HTTP 429: SEC EDGAR rate limit exceeded after 3 retries",
      "occurred_at": "2026-03-22T10:01:15Z"
    }
  ]
}
```

| Field | Type | Always present | Notes |
|---|---|---|---|
| `run_id` | `string` | Yes | UUID |
| `ticker` | `string\|null` | Yes | null for scheduled runs |
| `triggered_by` | `string` | Yes | `"api"` or `"schedule"` |
| `started_at` | `string` | Yes | ISO 8601 UTC |
| `completed_at` | `string\|null` | Yes | null while in progress |
| `filings_fetched` | `integer` | Yes | Successful fetches |
| `chunks_indexed` | `integer` | Yes | Total chunks written |
| `filings_skipped` | `integer` | Yes | Deduplicated filings |
| `failures` | `array` | Yes | Empty array if none |
| `failures[].accession_number` | `string\|null` | Yes | null if fetch failed before ID known |
| `failures[].source_url` | `string` | Yes | |
| `failures[].error_type` | `string` | Yes | |
| `failures[].error_message` | `string` | Yes | |
| `failures[].occurred_at` | `string` | Yes | ISO 8601 UTC |

### Error Responses

| Status | Condition |
|---|---|
| 404 | `run_id` not found |
| 422 | Invalid ticker format or field constraint violation |

---

## GET /api/v1/ingest/schedule

Returns the current ingestion schedule configuration.

### Response — 200 OK

```json
{
  "enabled": true,
  "cron_expression": "0 6 * * 1",
  "description": "Every Monday at 06:00 UTC",
  "next_run_at": "2026-03-23T06:00:00Z",
  "last_run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "last_run_completed_at": "2026-03-16T06:14:22Z"
}
```
