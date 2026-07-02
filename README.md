# Fintelligence — Earnings Intelligence Platform

A production-grade **hybrid RAG system** for financial research. Ask natural language questions about earnings filings and get structured, cited answers sourced exclusively from SEC EDGAR.

> *"Which semiconductor companies are guiding down gross margins?"* → Structured response with company metrics and SEC filing citations, in under 1 second (cached).

---

## Architecture

```
Query (natural language)
    ↓
Redis Cache (SHA-256 key, 1h TTL)  ──── cache hit ──→ Response
    ↓ cache miss
Hybrid Retrieval
  ├── Pinecone (dense vector, text-embedding-3-large)
  └── Elasticsearch BM25 (keyword)
    ↓ RRF fusion (k=60)
Cohere Rerank (top-10 candidates)
    ↓
GPT-4 Turbo → Pydantic-validated structured output
    ↓
Response { companies: [...], cite: "accession_page" }
```

**All data is sourced from SEC EDGAR only.** Every result includes a `cite` field pointing to the exact filing page — no exceptions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111 + Pydantic v2 |
| Embeddings | OpenAI `text-embedding-3-large` |
| Vector Store | Pinecone (serverless, cosine, 1536 dims) |
| Keyword Search | Elasticsearch 8.x + BM25 |
| Reranker | Cohere `rerank-english-v3.0` |
| LLM | GPT-4 Turbo (`gpt-4-turbo-2024-04-09`) |
| Cache | Redis (1h TTL) |
| Scheduler | APScheduler (weekly ingestion, Mon 06:00 UTC) |
| Data Source | SEC EDGAR API (10-K, 10-Q) |

---

## Prerequisites

- Python 3.11+
- Docker (for Elasticsearch and Redis)
- API keys: **OpenAI**, **Pinecone**, **Cohere**
- SEC EDGAR User-Agent string (required by EDGAR fair-access policy)

---

## Getting Started

### 1. Configure environment

```bash
cd backend/
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=earnings-chunks
COHERE_API_KEY=...
EDGAR_USER_AGENT="YourName contact@yourfund.com"
REDIS_URL=redis://localhost:6379/0
ELASTICSEARCH_URL=http://localhost:9200
LOG_RETENTION_DAYS=90
INGESTION_CRON="0 6 * * 1"
```

### 2. Start local dependencies

```bash
docker compose up -d elasticsearch redis
```

### 3. Install Python dependencies

```bash
python -m venv .venv && source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate                        # Windows
pip install -r requirements.txt
```

### 4. Initialize indexes

```bash
# Pinecone serverless index (1536 dims, cosine)
python -m src.services.ingestion.init_indexes

# Elasticsearch index with BM25 mapping
python -m src.services.ingestion.init_es_index
```

### 5. Ingest filings

```bash
# Ingest NVIDIA's most recent 4 filings (10-K + 10-Q)
python -m src.services.ingestion.cli --ticker NVDA --max-filings 4
```

### 6. Start the API

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the web UI at **http://localhost:8000**

---

## API

### `POST /api/v1/query`

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "What is NVIDIA gross margin guidance?"}'
```

```json
{
  "query_text": "What is NVIDIA gross margin guidance?",
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
  "cache_hit": false,
  "generated_at": "2026-03-22T10:00:00Z"
}
```

Optional filters: `fiscal_period_filter` (e.g. `"Q3 2024"`) and `ticker_filter` (e.g. `["NVDA", "AMD"]`).

### `GET /api/v1/health`

Returns liveness status for all dependencies (Pinecone, Elasticsearch, Redis, OpenAI, Cohere).

---

## Testing

```bash
pytest backend/tests/unit/ -v
pytest backend/tests/contract/ -v       # requires running API
pytest backend/tests/integration/ -v    # requires seeded indexes
```

### Latency benchmarks

```bash
python -m tests.benchmarks.query_latency --queries 20 --mode cached    # p95 < 1s
python -m tests.benchmarks.query_latency --queries 20 --mode uncached  # p95 < 10s
```

---

## Project Structure

```
backend/
├── src/
│   ├── api/            # FastAPI routers (/query, /ingest, /health)
│   ├── models/         # Pydantic schemas
│   ├── services/
│   │   ├── ingestion/  # SEC EDGAR fetch, chunking, dual indexing
│   │   ├── retrieval/  # Pinecone + BM25 + RRF fusion
│   │   ├── query/      # Full query pipeline
│   │   └── cache/      # Redis cache layer
│   ├── scheduler/      # Weekly ingestion job
│   └── static/         # Web UI (HTML/JS, no build step)
└── tests/
    ├── unit/
    ├── contract/
    ├── integration/
    └── benchmarks/
specs/
└── 001-earnings-intelligence-rag/   # Spec, plan, contracts, data model
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `cite` is null in response | LLM hallucination / insufficient data | Check retrieval scores in QueryLog; seed more filings |
| Pinecone 404 on upsert | Index not initialized | Re-run `init_indexes` |
| ES connection refused | Docker not running | `docker compose up -d elasticsearch` |
| EDGAR 429 on ingestion | Rate limit | Ingestion retries automatically; wait and re-trigger |
| Uncached query > 10s | Cohere rerank timeout | Check Cohere API status; reduce top-N in retrieval config |
