# Research: Earnings Intelligence Platform

**Branch**: `001-earnings-intelligence-rag` | **Date**: 2026-03-22
**Purpose**: Resolve all technical unknowns before design. All decisions below inform
`data-model.md`, `contracts/`, and implementation tasks.

---

## R-001: SEC EDGAR Data Acquisition

**Decision**: Use the SEC EDGAR full-text search API (`https://efts.sec.gov/LATEST/search-index`)
and the EDGAR filing viewer endpoint to fetch 10-K and 10-Q documents by CIK and
accession number. Earnings call transcripts are not available via EDGAR directly —
they are assumed available via EDGAR (as per spec assumption) or deferred to a
future data provider integration.

**Rationale**: SEC EDGAR provides machine-readable XBRL-tagged filings at no cost
with documented rate limits (10 req/s). Direct API access ensures data provenance
and supports the constitution's financial data integrity principle.

**Alternatives considered**:
- Third-party financial data vendors (Bloomberg, Refinitiv): cost-prohibitive,
  adds external dependency risk, and introduces data-chain attribution complexity.
- Web scraping EDGAR HTML pages: fragile, violates EDGAR terms for bulk access.

**Rate limiting**: EDGAR enforces 10 requests/second. Ingestion MUST use async
HTTP with a token-bucket rate limiter capped at 8 req/s (buffer for safety).
On 429 responses, exponential backoff with 3 retries before failing the document.

---

## R-002: Document Chunking Strategy

**Decision**: Fixed-size chunking at **512 tokens** with **50-token overlap**, using
`tiktoken` with the `cl100k_base` encoding (matches OpenAI embedding model tokenizer).
Each chunk retains parent metadata: filing accession number, CIK, filing type,
fiscal period, and page number estimate derived from character offset.

**Rationale**: 512-token chunks balance retrieval precision (too large = noise,
too small = missing context) for financial narrative. 50-token overlap prevents
sentences straddling chunk boundaries from being lost. Page number estimation from
character offset is sufficient for citation purposes on standard SEC filings.

**Alternatives considered**:
- Semantic/sentence-level chunking (e.g., LangChain `RecursiveCharacterTextSplitter`):
  produces variable-length chunks that complicate BM25 scoring normalization.
- Paragraph-level chunking: inconsistent paragraph sizes in SEC filings (tables,
  footnotes) create very short or very long chunks.

---

## R-003: Embedding Model and Vector Index Configuration

**Decision**: `text-embedding-3-large` (OpenAI) at **1536 dimensions** (half of
maximum 3072, achieved via the `dimensions` parameter). Pinecone serverless index,
cosine similarity metric, `us-east-1` region.

**Rationale**: 1536 dims provides ~97% of the quality of full 3072 dims at half
the storage cost and latency. Pinecone serverless eliminates pod sizing decisions
at current scale (50K chunks ≈ 400MB at 1536 dims × float32).

**Alternatives considered**:
- Full 3072 dims: doubles storage/cost with marginal quality gain at this corpus size.
- Open-source embedding models (e.g., `bge-large-en-v1.5`): lower quality on
  financial domain, requires self-hosted GPU inference.
- Weaviate / Qdrant: comparable quality but Pinecone serverless has better managed
  scaling and simpler SDK for a small team.

---

## R-004: Keyword Index and BM25 Configuration

**Decision**: Elasticsearch 8.x with a dedicated `earnings_chunks` index. Index
mapping uses `text` field with `english` analyzer for chunk content, plus `keyword`
fields for CIK, ticker, filing type, and fiscal period for filtering.

**Rationale**: Elasticsearch's BM25 implementation is production-grade and supports
the date-range and ticker filtering required by FR-011. The `english` analyzer
applies stemming relevant for financial terminology (e.g., "guiding" → "guid").

**Alternatives considered**:
- Solr: equivalent capability but smaller Python ecosystem support.
- Typesense / Meilisearch: simpler but lack the filter/aggregation depth needed
  for fiscal period filtering.
- Pure BM25 library (rank_bm25): in-memory only; cannot handle 50K+ chunks durably.

---

## R-005: Retrieval Fusion Strategy

**Decision**: **Reciprocal Rank Fusion (RRF)** with `k=60` constant. Retrieve
top-50 candidates from each of Pinecone and Elasticsearch independently, then fuse
rankings using RRF, producing a unified top-50 list passed to Cohere Rerank.

**Rationale**: RRF is parameter-light (only `k` to tune), robust to score scale
differences between vector (cosine similarity) and BM25 (TF-IDF score), and has
strong empirical results in hybrid retrieval literature. `k=60` is the standard
default with good out-of-the-box performance.

**Alternatives considered**:
- Linear score combination (weighted sum): requires normalizing incompatible score
  spaces (cosine vs BM25) and tuning per-query weights.
- Learned sparse retrieval (SPLADE): adds model hosting complexity with marginal
  benefit over BM25 for financial keyword matching.

---

## R-006: Reranking

**Decision**: Cohere `rerank-english-v3.0` model. Rerank the top-50 RRF candidates,
returning top-10 for LLM context. Maximum document length: 4096 tokens (Cohere limit).

**Rationale**: Cohere Rerank is explicitly called out in the project spec and
constitution as the ratified reranker. `rerank-english-v3.0` is the current
production model. Top-10 after reranking provides sufficient evidence for a
structured response covering up to 20 companies while staying within GPT-4 Turbo's
context window.

**Alternatives considered**:
- Cross-encoder models (e.g., `ms-marco-MiniLM`): self-hosted, adds GPU dependency.
- Skipping reranking: violates constitution Principle II (reranking is mandatory
  per FR-003).

---

## R-007: LLM Response Generation and Schema Validation

**Decision**: GPT-4 Turbo (`gpt-4-turbo-2024-04-09`) with OpenAI's structured
outputs (JSON mode + Pydantic schema). System prompt instructs the model to extract
only figures present in the retrieved chunks and cite the source chunk ID.
Pydantic v2 validates the response before it leaves the service boundary.

**Rationale**: GPT-4 Turbo's context window (128K tokens) comfortably fits 10
reranked chunks + system prompt. OpenAI's JSON mode + Pydantic integration enforces
schema compliance at the API level, providing an additional validation layer before
the application-level Pydantic check required by constitution Principle III.

**Alternatives considered**:
- GPT-4o: similar capability, slightly lower cost, but newer with less financial
  domain evaluation at time of spec; can be swapped in without architectural change.
- Local LLM (Llama 3): eliminates API cost but requires GPU hosting and lacks
  reliable structured output compliance for complex nested schemas.

---

## R-008: Query Caching

**Decision**: Redis (standalone, non-clustered at current scale) with a 1-hour TTL.
Cache key = SHA-256 hash of normalized query text (lowercased, stripped whitespace).
Cache stores the full serialized `QueryResult` JSON.

**Rationale**: Financial metric queries repeat frequently during earnings season
(e.g., all analysts asking about the same company's margins). 1-hour TTL balances
freshness (SEC filings don't change intra-day) with cache efficiency.

**Alternatives considered**:
- In-memory cache (functools.lru_cache): lost on restart, not shared across workers.
- Longer TTL (24h): acceptable but risks serving stale results if corpus is re-indexed
  mid-day after a late filing.

---

## R-009: Scheduled Ingestion

**Decision**: **APScheduler** (Advanced Python Scheduler) embedded in the FastAPI
application process. A `cron` trigger runs the full ingestion pipeline on a
configurable schedule (default: weekly on Monday 06:00 UTC, covering quarterly
earnings cadence with buffer). On-demand ingestion is exposed via REST API endpoint.

**Rationale**: APScheduler integrates directly with FastAPI's lifespan context,
requires no additional infrastructure (vs Celery + Redis broker), and is sufficient
for a small team with low ingestion frequency. If scale requires distributed workers,
migration to Celery is straightforward.

**Alternatives considered**:
- Celery + Redis: correct for high-volume, distributed workloads; over-engineered
  for single-tenant quarterly ingestion.
- External cron (crontab / AWS EventBridge): requires external orchestration; adds
  deployment complexity without benefit at current scale.

---

## R-010: Web UI Approach

**Decision**: Minimal static HTML + vanilla JavaScript served directly by FastAPI
from `backend/src/static/`. Single-page with: query input textarea, submit button,
results table (company, prior margin, guidance, change, citation link), and an
ingestion trigger form for operators.

**Rationale**: The spec calls for a "simple web UI — basic query form for non-technical
analysts". A self-contained HTML/JS page served by FastAPI eliminates npm, build
tools, and a separate deployment unit. Zero frontend dependencies to maintain.

**Alternatives considered**:
- React/Vite SPA: better DX for complex UIs, but adds npm pipeline and separate
  deployment step for a UI that is intentionally minimal.
- Streamlit: rapid prototyping but harder to integrate with existing FastAPI backend
  and looks non-professional for a hedge fund product.
