# Contract: Query API

**Branch**: `001-earnings-intelligence-rag` | **Date**: 2026-03-22
**Base URL**: `/api/v1`

---

## POST /api/v1/query

Submit a natural language financial query. Returns a structured, cited response.

### Request

```json
{
  "query_text": "Which semiconductor companies are guiding down gross margins?",
  "fiscal_period_filter": "Q3 2024",
  "ticker_filter": ["NVDA", "AMD", "INTC"]
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `query_text` | `string` | Yes | 1–2000 characters |
| `fiscal_period_filter` | `string` | No | e.g., `"Q3 2024"`, `"FY 2023"` |
| `ticker_filter` | `array[string]` | No | Uppercase ticker symbols; max 50 |

### Response — 200 OK

```json
{
  "query_text": "Which semiconductor companies are guiding down gross margins?",
  "companies": [
    {
      "name": "NVIDIA Corporation",
      "ticker": "NVDA",
      "metric_name": "gross_margin",
      "prior_value": 0.683,
      "current_value": 0.670,
      "change": -0.013,
      "unit": "ratio",
      "cite": "0001045810-24-000123_page_42"
    }
  ],
  "truncated": false,
  "explanation": null,
  "generated_at": "2026-03-22T10:00:00Z",
  "cache_hit": false
}
```

| Field | Type | Always present | Notes |
|---|---|---|---|
| `query_text` | `string` | Yes | Echo of request |
| `companies` | `array` | Yes | 0–20 entries |
| `companies[].name` | `string` | Yes | |
| `companies[].ticker` | `string` | Yes | |
| `companies[].metric_name` | `string` | Yes | |
| `companies[].prior_value` | `number\|null` | Yes | null if not found in source |
| `companies[].current_value` | `number\|null` | Yes | null if not found in source |
| `companies[].change` | `number\|null` | Yes | null if either value absent |
| `companies[].unit` | `string\|null` | Yes | |
| `companies[].cite` | `string` | Yes | NEVER null. Format: `{accession_number}_page_{N}` |
| `truncated` | `boolean` | Yes | true if >20 results capped |
| `explanation` | `string\|null` | Yes | Set when companies is empty |
| `generated_at` | `string` | Yes | ISO 8601 UTC datetime |
| `cache_hit` | `boolean` | Yes | |

### Error Responses

| Status | Condition | Body |
|---|---|---|
| 422 | Request validation failure | `{"detail": [...]}` (FastAPI default) |
| 500 | LLM response failed schema validation | `{"error": "upstream_validation_failure", "message": "..."}` |
| 503 | Retrieval service unavailable (Pinecone or ES) | `{"error": "retrieval_unavailable", "message": "..."}` |

### Caching Behaviour

- Cache key: SHA-256 of normalized `query_text` + `fiscal_period_filter` + sorted `ticker_filter`
- TTL: 1 hour
- `cache_hit: true` responses are served in < 1s (p95)
- Cache is bypassed if any filter combination has never been seen

---

## GET /api/v1/health

Liveness and dependency status check.

### Response — 200 OK

```json
{
  "status": "ok",
  "dependencies": {
    "pinecone": "ok",
    "elasticsearch": "ok",
    "redis": "ok",
    "openai": "ok",
    "cohere": "ok"
  }
}
```

A dependency in a degraded state returns `"degraded"` instead of `"ok"`. The
overall `status` is `"degraded"` if any dependency is degraded. Returns `200`
in both cases — `503` is reserved for complete service unavailability.
