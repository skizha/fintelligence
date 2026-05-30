# Fintelligence Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-22

## Active Technologies

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.11 |
| API Framework | FastAPI | 0.111 |
| Schema Validation | Pydantic | v2 |
| Vector Store | Pinecone (serverless, cosine, 1536 dims) | SDK v3 |
| Embeddings | OpenAI text-embedding-3-large | SDK v1 |
| Keyword Search | Elasticsearch + BM25 | 8.x |
| Reranker | Cohere rerank-english-v3.0 | SDK v5 |
| LLM | GPT-4 Turbo (gpt-4-turbo-2024-04-09) | OpenAI SDK v1 |
| Query Cache | Redis (1h TTL, SHA-256 cache key) | redis-py |
| Scheduler | APScheduler (embedded, cron trigger) | 3.x |
| HTTP Client | httpx (async, SEC EDGAR fetch) | latest |
| Tokenizer | tiktoken (cl100k_base, 512-token chunks) | latest |
| Testing | pytest + pytest-asyncio | latest |
| Web UI | Static HTML + vanilla JS (served by FastAPI) | N/A |

## Project Structure

```text
backend/
├── src/
│   ├── models/              # Pydantic schemas: QueryResult, IngestionReport, QueryLog, etc.
│   ├── services/
│   │   ├── ingestion/       # SEC EDGAR fetch, chunking (512 tok / 50 overlap), dual indexing
│   │   ├── retrieval/       # Pinecone dense + ES BM25, RRF fusion (k=60), Cohere rerank top-10
│   │   ├── query/           # Query pipeline: cache check → retrieve → rerank → generate → validate
│   │   └── cache/           # Redis layer (SHA-256 key on normalized query + filters)
│   ├── api/                 # FastAPI routers: /api/v1/query, /api/v1/ingest, /api/v1/health
│   ├── scheduler/           # APScheduler jobs (default: Mon 06:00 UTC)
│   └── static/              # Web UI: query form + results table (HTML/JS, no build step)
└── tests/
    ├── contract/            # Schema validation + API contract tests
    ├── integration/         # End-to-end pipeline tests against seeded indexes
    ├── unit/                # Isolated service unit tests
    └── benchmarks/          # Latency benchmarks (cached < 1s p95, uncached < 10s p95)

specs/
└── 001-earnings-intelligence-rag/
    ├── spec.md
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── contracts/
    │   ├── query-api.md
    │   └── ingestion-api.md
    └── tasks.md
```

## Commands

```bash
# Start local dependencies
docker compose up -d elasticsearch redis

# Install dependencies
pip install -r backend/requirements.txt

# Initialize indexes (run once)
python -m src.services.ingestion.init_indexes
python -m src.services.ingestion.init_es_index

# Ingest a ticker
python -m src.services.ingestion.cli --ticker NVDA --max-filings 4

# Start API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest backend/tests/unit/ -v
pytest backend/tests/contract/ -v
pytest backend/tests/integration/ -v

# Latency benchmark (must pass before PR)
python -m tests.benchmarks.query_latency --queries 20 --mode cached
python -m tests.benchmarks.query_latency --queries 20 --mode uncached
```

## Code Style

- **Pydantic v2**: Use `model_validator`, `field_validator`; avoid v1 `@validator` syntax.
- **Async-first**: All I/O (Pinecone, ES, OpenAI, Cohere, Redis, httpx) MUST use `async/await`.
- **No silent failures**: All ingestion failures MUST be logged to `IngestionFailure`; never swallowed.
- **Schema validation is mandatory**: Every LLM response MUST pass Pydantic validation before return.
  On failure: log, raise `ValidationError`, return HTTP 500 — never return unvalidated data.
- **Citations are non-negotiable**: If a `CompanyResult` cannot have a `cite` field, omit the entry.
- **BM25 + vector always**: Never call Pinecone without also calling Elasticsearch. RRF fuses both.

## Constitution Principles (summary for development)

1. **Data Integrity**: SEC EDGAR only. `cite` on every result. No exceptions.
2. **Hybrid Retrieval**: Pinecone + ES/BM25 + Cohere rerank. All three. Every query.
3. **Structured Output**: Pydantic-validated. Invalid → reject and log.
4. **Performance**: Cached p95 < 1s. Uncached p95 < 10s. Benchmark before merge.
5. **Observability**: `QueryLog` and `IngestionReport` written for every execution.

## Recent Changes

- **001-earnings-intelligence-rag** (2026-03-22): Initial platform — hybrid RAG pipeline,
  SEC EDGAR ingestion with scheduling, FastAPI REST + static web UI, full audit logging.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
