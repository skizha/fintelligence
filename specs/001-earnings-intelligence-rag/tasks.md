---

description: "Task list for Earnings Intelligence Platform implementation"
---

# Tasks: Earnings Intelligence Platform

**Input**: Design documents from `/specs/001-earnings-intelligence-rag/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Contract and integration tests included in Polish phase to validate
constitution compliance (Principles I–V). TDD not explicitly requested.

**Organization**: Tasks grouped by user story to enable independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- Exact file paths included in all task descriptions

## Path Conventions

- Backend source: `backend/src/`
- Tests: `backend/tests/{unit/, contract/, integration/, benchmarks/}`
- Static web UI: `backend/src/static/`
- Specs: `specs/001-earnings-intelligence-rag/`

---

## Phase 1: Setup

**Purpose**: Project initialization and directory structure

- [x] T001 Create full directory tree per plan.md: `backend/src/{models/,services/{ingestion/,retrieval/,query/,cache/},api/routers/,scheduler/,static/}` and `backend/tests/{unit/,contract/,integration/,benchmarks/}` with `__init__.py` in each Python package
- [x] T002 Create `backend/requirements.txt` with pinned versions: fastapi==0.111.*, pydantic>=2.0, pinecone-client>=3, openai>=1, elasticsearch>=8, cohere>=5, redis, apscheduler==3.*, httpx, tiktoken, uvicorn, pytest, pytest-asyncio
- [x] T003 [P] Create `backend/.env.example` with all required env vars: `OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `COHERE_API_KEY`, `EDGAR_USER_AGENT`, `REDIS_URL`, `ELASTICSEARCH_URL`, `LOG_RETENTION_DAYS=90`, `INGESTION_CRON="0 6 * * 1"`
- [x] T004 [P] Create `docker-compose.yml` at repo root with Elasticsearch 8.x and Redis services, health checks, and named volumes
- [x] T005 [P] Create `backend/pytest.ini` configuring asyncio mode, testpaths for all test directories, and log level

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on before any feature work begins

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create all Pydantic v2 entity schemas in `backend/src/models/schemas.py`: `Filing`, `Chunk`, `QueryRequest`, `CompanyResult`, `QueryResult`, `IngestionReport`, `IngestionFailure`, `QueryLog` — field types, constraints, and validators exactly as defined in `specs/001-earnings-intelligence-rag/data-model.md`
- [x] T007 [P] Create `backend/src/services/ingestion/init_indexes.py`: initialize Pinecone serverless index named `earnings-chunks` with 1536 dims, cosine metric, `us-east-1` region; idempotent (skip if exists)
- [x] T008 [P] Create `backend/src/services/ingestion/init_es_index.py`: create Elasticsearch index `earnings_chunks` with mapping — `text` field using `english` analyzer, `ticker`/`filing_type`/`fiscal_period` as `keyword`, `period_date` as `date`, `chunk_id` as `keyword` primary key; idempotent
- [x] T009 [P] Create `backend/src/services/logging.py`: structured JSON logger emitting to stdout; helper `write_query_log(log: QueryLog)` and `write_ingestion_report(report: IngestionReport)` that assert `retention_until >= now + 90 days`
- [x] T010 [P] Create `backend/src/api/main.py`: FastAPI app with lifespan context, include routers placeholder, mount `backend/src/static/` at `/`; configure CORS for local dev

**Checkpoint**: Indexes initialized, schemas importable, logger usable — user story implementation can begin

---

## Phase 3: User Story 1 — Natural Language Financial Query (Priority: P1) 🎯 MVP

**Goal**: Analyst submits a natural language query, receives a cited structured JSON response in < 1s (cached) or < 10s (uncached).

**Independent Test**: Seed index with NVDA filing chunks (use init scripts + manual upsert), POST to `/api/v1/query` with "What is NVIDIA gross margin guidance?", assert response has ≥1 company with non-null `cite`.

### Implementation for User Story 1

- [x] T011 [P] [US1] Create `backend/src/services/retrieval/pinecone_retriever.py`: async function `retrieve_dense(query_text, filters, top_k=50) -> list[ScoredChunk]` — embed query with `text-embedding-3-large` (1536 dims), query Pinecone with metadata filters for `ticker_filter` and `fiscal_period_filter`, return chunk IDs and scores
- [x] T012 [P] [US1] Create `backend/src/services/retrieval/es_retriever.py`: async function `retrieve_sparse(query_text, filters, top_k=50) -> list[ScoredChunk]` — BM25 query against `earnings_chunks` index with `english` analyzer, apply `ticker` and `fiscal_period` keyword filters, return chunk IDs and BM25 scores
- [x] T013 [US1] Create `backend/src/services/retrieval/rrf_fusion.py`: function `fuse_rrf(dense_results, sparse_results, k=60) -> list[str]` implementing Reciprocal Rank Fusion; merge top-50 from each retriever, return unified top-50 chunk IDs ordered by fused score (depends on T011, T012 interfaces)
- [x] T014 [P] [US1] Create `backend/src/services/retrieval/cohere_reranker.py`: async function `rerank(query_text, chunk_ids, chunks_text) -> list[RankedChunk]` — call Cohere `rerank-english-v3.0`, max 4096 tokens per doc, return top-10 with reranker scores
- [x] T015 [P] [US1] Create `backend/src/services/cache/query_cache.py`: async `get(cache_key: str) -> QueryResult | None` and `set(cache_key, result, ttl=3600)`; cache key = SHA-256 of normalized `query_text + fiscal_period_filter + sorted(ticker_filter)`; uses Redis via `REDIS_URL`
- [x] T016 [P] [US1] Create `backend/src/services/query/llm_generator.py`: async `generate(query_text, ranked_chunks) -> QueryResult` — system prompt instructs GPT-4 Turbo to extract only figures present in chunks and cite source chunk ID; validate response with Pydantic `QueryResult`; on validation failure raise `LLMValidationError` (never return unvalidated data)
- [x] T017 [US1] Create `backend/src/services/query/query_logger.py`: `write_query_log(query_request, result, scores, latency_ms)` building a `QueryLog` with `retention_until = today + 90 days` and calling `logging.write_query_log()` (depends T006, T009)
- [x] T018 [US1] Create `backend/src/services/query/pipeline.py`: async `run_query(request: QueryRequest) -> QueryResult` orchestrating: (1) cache lookup → return if hit, (2) parallel dense+sparse retrieval, (3) RRF fusion, (4) Cohere rerank, (5) LLM generate+validate, (6) cache write, (7) query log write; set `cache_hit` flag; enforce 20-company cap + `truncated` flag (depends T011–T017)
- [x] T019 [US1] Create `backend/src/api/routers/query.py`: `POST /api/v1/query` accepting `QueryRequest`, calling `pipeline.run_query()`, returning `QueryResult`; HTTP 500 on `LLMValidationError`; HTTP 503 on retrieval service failure; register router in `backend/src/api/main.py`
- [x] T020 [P] [US1] Create `backend/src/api/routers/health.py`: `GET /api/v1/health` pinging Pinecone, Elasticsearch, Redis, OpenAI, and Cohere; return `{"status": "ok"|"degraded", "dependencies": {...}}`; register router in `backend/src/api/main.py`
- [x] T021 [P] [US1] Create `backend/src/static/index.html`: single-page HTML with query textarea, optional fiscal period and ticker filter inputs, Submit button, results table (Company, Ticker, Metric, Prior, Current, Change, Citation); vanilla JS fetch to `POST /api/v1/query`; display `truncated` warning banner when true

**Checkpoint**: User Story 1 fully functional — POST /api/v1/query returns cited JSON; web UI renders results; cache_hit=true on repeated query

---

## Phase 4: User Story 2 — Automated Earnings Document Ingestion (Priority: P2)

**Goal**: Operator triggers ingestion for a ticker; system fetches from SEC EDGAR, chunks, dual-indexes, and returns a structured report. Runs on schedule and on demand.

**Independent Test**: Run `python -m src.services.ingestion.cli --ticker NVDA --max-filings 1`, assert `IngestionReport.filings_fetched >= 1` and chunk appears in Elasticsearch via keyword search.

### Implementation for User Story 2

- [x] T022 [P] [US2] Create `backend/src/services/ingestion/edgar_client.py`: async `fetch_filings(ticker, filing_types, max_filings) -> list[FilingDocument]` — call SEC EDGAR full-text search API with `User-Agent` header from env; enforce 8 req/s rate limit (token-bucket); exponential backoff on 429 (3 retries); return raw text + accession number + CIK + filing type + period date + source URL
- [x] T023 [P] [US2] Create `backend/src/services/ingestion/chunker.py`: `chunk_document(text, accession_number, metadata) -> list[Chunk]` — fixed 512-token chunks with 50-token overlap using `tiktoken cl100k_base`; estimate `page_number` from character offset (char_offset / avg_chars_per_page); set `chunk_id = {accession_number}_chunk_{index}`; validate `token_count <= 512`
- [x] T024 [US2] Create `backend/src/services/ingestion/indexer.py`: async `index_chunks(chunks: list[Chunk])` — parallel upsert to Pinecone (batch 100, embed with `text-embedding-3-large`) and Elasticsearch (bulk index); fail atomically per chunk (both indexes or neither); log per-chunk failures as `IngestionFailure` (depends T022, T023 interfaces)
- [x] T025 [US2] Create `backend/src/services/ingestion/pipeline.py`: async `run_ingestion(ticker, filing_types, max_filings, triggered_by) -> IngestionReport` — (1) fetch filings from EDGAR, (2) deduplicate by accession number (skip if already indexed), (3) chunk each filing, (4) index chunks, (5) write `IngestionReport` via logger; handle image-only PDFs (skip + warn); never partially index a filing (depends T022–T024)
- [x] T026 [US2] Create `backend/src/scheduler/ingestion_job.py`: APScheduler `CronTrigger` job calling `ingestion_pipeline.run_ingestion()` for all tickers in watchlist; read schedule from `INGESTION_CRON` env var (default `0 6 * * 1`); integrate into FastAPI lifespan in `backend/src/api/main.py`
- [x] T027 [US2] Create `backend/src/api/routers/ingestion.py`: `POST /api/v1/ingest` returning 202 with `run_id`; `GET /api/v1/ingest/{run_id}` returning current `IngestionReport`; `GET /api/v1/ingest/schedule` returning schedule config and next run time; register all three routes in `backend/src/api/main.py` (depends T025)
- [x] T028 [P] [US2] Create `backend/src/services/ingestion/cli.py`: `python -m src.services.ingestion.cli --ticker TICKER --max-filings N` CLI wrapping `ingestion_pipeline.run_ingestion()`; print `IngestionReport` as formatted JSON to stdout
- [x] T029 [P] [US2] Add ingestion operator section to `backend/src/static/index.html`: ticker input + "Ingest" button; JS polls `GET /api/v1/ingest/{run_id}` every 3s until `completed_at` is set; display filings fetched, chunks indexed, failures list

**Checkpoint**: User Story 2 fully functional — ingest NVDA via CLI or UI, verify chunks indexed in both Pinecone and Elasticsearch

---

## Phase 5: User Story 3 — Query Result Citation and Auditability (Priority: P3)

**Goal**: Every `cite` field in a response resolves to a specific SEC filing page. Audit log entries persist for ≥ 90 days.

**Independent Test**: Submit query, extract `cite` value (e.g., `0001045810-24-000123_page_42`), parse accession number and page, confirm figure appears in filing on that page.

### Implementation for User Story 3

- [x] T030 [P] [US3] Create `backend/src/services/query/citation_validator.py`: `validate_citations(result: QueryResult) -> list[CitationIssue]` — parse each `cite` field (format: `{accession_number}_page_{N}`), verify accession number exists in Elasticsearch index, return list of issues for any that don't resolve; log issues but do not block response
- [x] T031 [US3] Wire `citation_validator.validate_citations()` into `backend/src/services/query/pipeline.py` after LLM generation — run validation, append issues to `QueryLog.citations_returned`; if a `CompanyResult.cite` is null or malformed, remove that entry from results before return (depends T030, T018)
- [x] T032 [US3] Update `backend/src/services/query/query_logger.py` to persist `QueryLog` with full `citations_returned` list and assert `retention_until >= today + 90 days`; write to append-only structured log file at `logs/query_audit.jsonl` (depends T017)
- [x] T033 [P] [US3] Enhance `backend/src/static/index.html`: render each citation as a hyperlink to the SEC EDGAR filing viewer URL (`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={filing_type}`); display `accession_number` and `page_number` as tooltip

**Checkpoint**: All three user stories complete and independently testable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, benchmarks, and deployment readiness

- [x] T034 [P] Write contract test `backend/tests/contract/test_query_schema.py`: POST `/api/v1/query` with valid request, assert response matches `QueryResult` schema; assert `cite` present on every `CompanyResult`; assert `truncated` field always present; assert 422 on missing `query_text`
- [x] T035 [P] Write contract test `backend/tests/contract/test_ingestion_schema.py`: POST `/api/v1/ingest`, assert 202 + `run_id`; GET `/api/v1/ingest/{run_id}`, assert response matches `IngestionReport` schema; assert 404 on unknown `run_id`
- [x] T036 [P] Write integration test `backend/tests/integration/test_pipeline_e2e.py`: seed index with 5 NVDA chunks (known content), POST query for known metric, assert ≥1 company returned, assert `cite` resolves to seeded accession number, assert `cache_hit=true` on second identical call
- [x] T037 [P] Write unit test `backend/tests/unit/test_rrf_fusion.py`: assert RRF with k=60 correctly merges overlapping and disjoint result lists; assert output length ≤ 50; assert higher-ranked items in both lists score higher
- [x] T038 [P] Write unit test `backend/tests/unit/test_chunker.py`: assert chunk token count ≤ 512; assert overlap produces shared tokens at chunk boundaries; assert `chunk_id` format matches `{accession_number}_chunk_{index}`; assert `page_number ≥ 1`
- [x] T039 [P] Create `backend/tests/benchmarks/query_latency.py`: `--mode cached` runs 20 identical queries and asserts p95 < 1000ms; `--mode uncached` clears cache and runs 20 unique queries asserting p95 < 10000ms; prints timing table to stdout
- [x] T040 [P] Create `backend/Dockerfile`: multi-stage build, Python 3.11 slim base, non-root user, copy `backend/` contents, `CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- [x] T041 [P] Update `CLAUDE.md` with final actual source paths, any patterns discovered during implementation, and confirmed latency benchmark results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T003–T005 parallel
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories; T007–T010 parallel within phase
- **User Story 1 (Phase 3)**: Depends on Foundational — T011+T012 parallel start; T013 after both; T014+T015+T016+T017 parallel; T018 after all; T019+T020+T021 after T018 or independent
- **User Story 2 (Phase 4)**: Depends on Foundational — T022+T023 parallel start; T024 after both; T025 → T026 → T027; T028+T029 parallel after T025
- **User Story 3 (Phase 5)**: Depends on US1 pipeline (T018) and US2 indexer (T024); T030+T033 parallel; T031 after T030; T032 after T017
- **Polish (Phase 6)**: Depends on all user stories complete; all tasks parallel

### Within User Story 1

```
T011 ──┐
       ├──► T013 ──► T018 ──► T019
T012 ──┘                 ↑
T014 ────────────────────┤
T015 ────────────────────┤
T016 ────────────────────┘
T017 ────────────────────┘
T020 (after T019, register router)
T021 [P] independent
```

### Within User Story 2

```
T022 ──┐
       ├──► T024 ──► T025 ──► T026 ──► T027
T023 ──┘                           └──► T028 [P]
                                   └──► T029 [P]
```

### Parallel Opportunities by Phase

```bash
# Phase 2 — run simultaneously:
Task: "T007 Create Pydantic schemas"
Task: "T008 Initialize Pinecone index"
Task: "T009 Initialize Elasticsearch index"
Task: "T010 Create structured logger"

# Phase 3 (US1) — first parallel batch:
Task: "T011 Pinecone dense retriever"
Task: "T012 Elasticsearch BM25 retriever"
Task: "T014 Cohere reranker"
Task: "T015 Redis query cache"
Task: "T016 LLM generator"

# Phase 6 — all parallel:
Task: "T034 Contract tests: query API"
Task: "T035 Contract tests: ingestion API"
Task: "T036 Integration test: e2e pipeline"
Task: "T037 Unit tests: RRF fusion"
Task: "T038 Unit tests: chunker"
Task: "T039 Latency benchmark script"
Task: "T040 Dockerfile"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (T011–T021)
4. **STOP AND VALIDATE**: seed index with NVDA chunks, run query, confirm cited JSON, confirm cache
5. Deploy MVP — analysts can query the seeded corpus

### Incremental Delivery

1. Setup + Foundational → initialize indexes
2. User Story 1 → query pipeline live → **Demo to analysts**
3. User Story 2 → ingest pipeline + scheduler → **Corpus grows automatically**
4. User Story 3 → citation audit trail → **Compliance-ready**
5. Polish → tests + benchmark + Docker → **Production-ready**

### Parallel Team Strategy

With two developers:

- **Dev A** after Foundational: User Story 1 (T011–T021)
- **Dev B** after Foundational: User Story 2 (T022–T029)
- Both converge for User Story 3 and Polish

---

## Notes

- `[P]` tasks operate on different files with no unresolved dependencies
- `[Story]` label maps each task to its user story for traceability
- Schema validation (T016) MUST reject on failure — never return unvalidated LLM output
- BM25 (T012) MUST always run alongside Pinecone (T011) — neither may be skipped in pipeline (T018)
- `cite` field MUST always be present on `CompanyResult` — entries without a source MUST be dropped (T031)
- Run latency benchmark (T039) before any PR merge to verify constitution Principle IV
- Commit after each checkpoint; each checkpoint should be independently deployable
