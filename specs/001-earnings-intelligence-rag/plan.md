# Implementation Plan: Earnings Intelligence Platform

**Branch**: `001-earnings-intelligence-rag` | **Date**: 2026-03-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-earnings-intelligence-rag/spec.md`

## Summary

Build a production RAG system that lets hedge fund analysts query 500+ SEC earnings
filings in natural language and receive structured, cited JSON responses in under 1
second (cached) or 10 seconds (uncached). The pipeline combines Pinecone vector
search with Elasticsearch BM25, fused via Reciprocal Rank Fusion and reranked with
Cohere, before GPT-4 Turbo generates a Pydantic-validated structured response.
A FastAPI backend serves both a REST API and a minimal static web UI for analysts.
Scheduled + on-demand ingestion fetches 10-K/10-Q filings from SEC EDGAR directly.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI 0.111, Pydantic v2, Pinecone SDK v3, OpenAI SDK v1,
  elasticsearch-py 8.x, cohere SDK v5, Redis (via redis-py), APScheduler 3.x,
  httpx (SEC EDGAR async fetch), tiktoken (chunking)
**Storage**: Pinecone (vector index, 50K+ chunks), Elasticsearch 8.x (BM25 keyword
  index), Redis (query response cache)
**Testing**: pytest, pytest-asyncio, httpx (test client)
**Target Platform**: Linux server (containerized via Docker)
**Project Type**: Web service (FastAPI REST API + static HTML/JS web UI served by FastAPI)
**Performance Goals**: p95 < 1s for cached queries; p95 < 10s for uncached queries
**Constraints**: 50K+ document chunks from launch; no formal uptime SLA; PII must
  never enter vector or keyword index; all LLM responses validated before return
**Scale/Scope**: Small analyst team (<50 users); single-tenant; quarterly ingestion
  cadence + on-demand per ticker

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Financial Data Integrity | All data sourced from SEC EDGAR API; every response includes `cite` field | ✅ PASS — FR-005 mandates SEC EDGAR; FR-004 mandates `cite` on every result |
| II. Hybrid Retrieval (NON-NEGOTIABLE) | Pinecone dense + Elasticsearch BM25 used for every production query | ✅ PASS — FR-002 explicitly prohibits skipping either mode |
| III. Structured Output (NON-NEGOTIABLE) | All LLM responses validated against Pydantic schema before return | ✅ PASS — FR-009 mandates rejection of invalid responses |
| IV. Sub-Second Performance | Cached p95 < 1s; uncached p95 < 10s; latency benchmark required | ✅ PASS — FR-010 + SC-001 define targets; benchmark in quickstart.md |
| V. Observability & Audit Trail | Structured logs for every query and ingestion run; 90-day retention | ✅ PASS — FR-007 + FR-008 define required log fields; SC-006 mandates 90-day retention |

**GATE RESULT: ALL PASS — proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-earnings-intelligence-rag/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── query-api.md
│   └── ingestion-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/              # Pydantic schemas (QueryResult, IngestionReport, QueryLog…)
│   ├── services/
│   │   ├── ingestion/       # SEC EDGAR fetch, chunking, embedding, dual indexing
│   │   ├── retrieval/       # Pinecone dense + ES BM25 + RRF fusion + Cohere rerank
│   │   ├── query/           # Query pipeline orchestration (cache → retrieve → generate)
│   │   └── cache/           # Redis query cache layer
│   ├── api/                 # FastAPI routers (query, ingestion, health)
│   ├── scheduler/           # APScheduler jobs (scheduled ingestion runs)
│   └── static/              # Minimal HTML/JS web UI (served by FastAPI)
└── tests/
    ├── contract/            # Schema validation + API contract tests
    ├── integration/         # End-to-end pipeline tests against real/seeded indexes
    └── unit/                # Isolated service unit tests

```

**Structure Decision**: Web service with FastAPI serving both the REST API and a
minimal static HTML/JS UI from `backend/src/static/`. No separate frontend build
pipeline — keeps the stack simple for a small analyst team. Single Docker container
for the backend; external managed services for Pinecone, Elasticsearch, and Redis.

## Complexity Tracking

> No constitution violations requiring justification.
