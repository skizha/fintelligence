# Quickstart: Earnings Intelligence Platform

**Branch**: `001-earnings-intelligence-rag` | **Date**: 2026-03-22

---

## Prerequisites

- Python 3.11+
- Docker (for Elasticsearch and Redis)
- API keys: OpenAI, Pinecone, Cohere
- SEC EDGAR User-Agent string (required by EDGAR fair-access policy)

---

## 1. Environment Setup

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
EDGAR_USER_AGENT="YourFund contact@yourfund.com"
REDIS_URL=redis://localhost:6379/0
ELASTICSEARCH_URL=http://localhost:9200
LOG_RETENTION_DAYS=90
INGESTION_CRON="0 6 * * 1"
```

---

## 2. Start Local Dependencies

```bash
docker compose up -d elasticsearch redis
```

Wait for Elasticsearch to be healthy:

```bash
curl -s http://localhost:9200/_cluster/health | python -m json.tool
# "status" should be "green" or "yellow"
```

---

## 3. Install Python Dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Initialize Indexes

```bash
# Create Pinecone serverless index (1536 dims, cosine)
python -m src.services.ingestion.init_indexes

# Create Elasticsearch earnings_chunks index with mapping
python -m src.services.ingestion.init_es_index
```

---

## 5. Ingest Sample Data (Validation)

Ingest NVIDIA's most recent filings to seed the system:

```bash
python -m src.services.ingestion.cli --ticker NVDA --max-filings 2
```

Expected output:

```
Fetching filings for NVDA from SEC EDGAR...
Fetched 2 filings (10-K: 1, 10-Q: 1)
Chunked: 921 chunks
Indexed to Pinecone: 921 vectors
Indexed to Elasticsearch: 921 documents
Skipped (duplicate): 0
Failures: 0
Run ID: f47ac10b-...
```

---

## 6. Start the API

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 7. Validate: Query API

```bash
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "What is NVIDIA gross margin guidance?"}' \
  | python -m json.tool
```

**Pass criteria**:
- HTTP 200
- Response contains `companies` array with at least 1 entry
- Each entry has a non-null `cite` field
- `cache_hit` is `false` on first call

Run the same query again — `cache_hit` MUST be `true` and latency < 1s:

```bash
time curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "What is NVIDIA gross margin guidance?"}' \
  > /dev/null
# real time should be < 1.0s
```

---

## 8. Validate: Web UI

Open `http://localhost:8000` in a browser. You should see:

- Query input textarea
- Submit button
- After submitting: results table with Company, Metric, Prior, Guidance, Change, Citation columns

---

## 9. Validate: Citation Traceability (Constitution Principle I)

Take a `cite` value from a query response, e.g., `0001045810-24-000123_page_42`:

1. Parse: accession number = `0001045810-24-000123`, page = `42`
2. Navigate to: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number-nodashes}/{document}`
3. Confirm the figure cited in the response appears on or near page 42 of the filing

---

## 10. Latency Benchmark (Constitution Principle IV)

```bash
# Run 20 unique queries (uncached) and report p95 latency
python -m tests.benchmarks.query_latency --queries 20 --mode uncached

# Run 20 repeated queries (cached) and report p95 latency
python -m tests.benchmarks.query_latency --queries 20 --mode cached
```

**Pass criteria**:
- Cached p95 < 1000ms
- Uncached p95 < 10000ms

---

## 11. Run Test Suite

```bash
# Unit tests
pytest tests/unit/ -v

# Contract tests (requires running API)
pytest tests/contract/ -v

# Integration tests (requires seeded index from step 5)
pytest tests/integration/ -v
```

All tests must pass before opening a PR.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `cite` field is null in response | LLM hallucinating without source | Check chunk retrieval scores in QueryLog; may need more seeded data |
| Pinecone 404 on upsert | Index not initialized | Re-run step 4 |
| ES connection refused | Docker not running | `docker compose up -d elasticsearch` |
| EDGAR 429 on ingestion | Rate limit hit | Ingestion retries automatically; wait and re-trigger |
| Uncached query > 10s | Cohere rerank timeout | Check Cohere API status; reduce top-N candidates in retrieval config |
