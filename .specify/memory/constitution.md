<!--
SYNC IMPACT REPORT
==================
Version change: [template] → 1.0.0
Modified principles: N/A (initial population from template placeholders)
Added sections:
  - Core Principles (I–V)
  - Technology Stack Constraints
  - Data, Compliance & Quality Standards
  - Governance
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md  ✅ Constitution Check gates derive from principles below
  - .specify/templates/spec-template.md  ✅ No structural changes required; FR/SC patterns align
  - .specify/templates/tasks-template.md ✅ Observability + structured-output task types now explicit
  - .specify/templates/commands/*.md     ✅ No agent-specific name collisions found
Follow-up TODOs:
  - TODO(RATIFICATION_DATE): Treat 2026-03-22 as adoption date; update if project predates this session.
-->

# Fintelligence Constitution

## Core Principles

### I. Financial Data Integrity

All financial data MUST be sourced exclusively from authoritative, machine-readable
primary sources (SEC EDGAR API: 10-K, 10-Q, earnings call transcripts). No
manually keyed or unverified third-party data is permitted in the retrieval corpus.

Every structured response MUST include a `cite` field referencing the originating
document, filing section, and page number. Responses without citations MUST be
rejected at the output validation layer.

**Rationale**: Hedge fund decisions based on unverified or incorrectly attributed
data create material financial and legal liability. Citation traceability is
non-negotiable.

### II. Hybrid Retrieval Architecture (NON-NEGOTIABLE)

Every query pipeline MUST combine:
- **Dense retrieval**: OpenAI `text-embedding-3-large` vectors in Pinecone
  (semantic similarity over financial narrative)
- **Sparse retrieval**: Elasticsearch + BM25 with date-range and ticker filters
  (exact term matching for figures, guidance language, and metrics)
- **Reranking**: Cohere Rerank (financial-domain model) applied after fusion

Single-mode retrieval (vector-only or keyword-only) is prohibited in production.
Retrieval ablation studies MUST be documented before any architectural change.

**Rationale**: Financial queries require both semantic understanding ("guiding down
margins") and precise term matching (specific percentages, fiscal periods, tickers).
Hybrid retrieval is the core IP of the system.

### III. Structured Output with Pydantic (NON-NEGOTIABLE)

All LLM responses MUST be validated against a Pydantic model before leaving the
service boundary. Free-form text responses to structured financial queries are
prohibited. Every response schema MUST include:
- Company identifiers (ticker, name)
- Numeric values with units and prior-period comparisons where applicable
- Source citation (`cite` field: `{document}_{page}`)
- Confidence or retrieval score where surfaced

**Rationale**: Downstream consumers (portfolio systems, analysts) depend on
machine-readable, schema-stable output. Schema drift silently corrupts downstream
analysis.

### IV. Sub-Second Performance for Cached Queries

Cached query responses MUST be served in under 1 second (p95). Uncached query
pipelines (retrieval + reranking + LLM) MUST complete in under 10 seconds (p95).
Every new endpoint MUST include a latency benchmark in its implementation plan.

Performance regressions exceeding 20% versus baseline MUST block merge until
root-caused and resolved or formally justified.

**Rationale**: Analysts run queries during live earnings calls and market hours.
Latency directly impairs the product's value.

### V. Observability & Audit Trail

Every query execution MUST emit structured logs containing: query text, retrieval
scores, reranker scores, model used, response latency, and the full citation set
returned. Logs MUST be retained for a minimum of 90 days.

All data ingestion runs (SEC EDGAR fetches) MUST be logged with: source URL,
document count, embedding count, timestamp, and any failures. Silent ingestion
failures are prohibited.

**Rationale**: Regulatory and operational audits of financial AI systems require
end-to-end traceability from query to evidence. Observability is also the primary
debugging surface for retrieval quality issues.

## Technology Stack Constraints

The following stack is ratified for production use. Substitutions require a
constitution amendment with documented rationale and migration plan.

| Layer | Ratified Technology |
|---|---|
| Document Source | SEC EDGAR API |
| Vector Store | Pinecone (target corpus: 50K+ documents) |
| Embeddings | OpenAI `text-embedding-3-large` |
| Sparse Search | Elasticsearch + BM25 |
| Reranker | Cohere Rerank (financial-tuned model) |
| LLM | GPT-4 Turbo |
| Output Validation | Pydantic structured output |
| Backend API | FastAPI |

Experimental or alternative components MUST be isolated behind feature flags and
MUST NOT share the production retrieval index without explicit approval.

## Data, Compliance & Quality Standards

- The retrieval corpus MUST only contain documents fetched directly from SEC EDGAR
  or equivalent regulatory filing systems. Web-scraped or redistributed data is
  prohibited.
- Document ingestion MUST validate filing type, CIK, accession number, and filing
  date before indexing.
- Personally Identifiable Information (PII) MUST NOT be stored in the vector index
  or returned in structured responses.
- Retrieval quality MUST be evaluated on a held-out benchmark of ≥50 financial
  queries per quarter. Results MUST be documented in `docs/retrieval-benchmarks/`.
- Any change to the embedding model or chunking strategy constitutes a MAJOR
  amendment and requires full re-indexing with quality validation before deployment.

## Governance

This constitution supersedes all other development practices, design docs, and
verbal agreements within the Fintelligence project. Conflicts default to the most
recent ratified version of this document.

**Amendment procedure**:
1. Propose change in a dedicated PR with `[constitution]` in the title.
2. Document the principle being added, modified, or removed, and justify the
   version bump type (MAJOR / MINOR / PATCH).
3. Update `LAST_AMENDED_DATE` and `CONSTITUTION_VERSION` in this file.
4. Run the `/speckit.constitution` command to propagate changes to dependent templates.
5. Obtain at least one peer review before merging.

**Versioning policy** (semantic):
- MAJOR: Principle removal, redefinition, or stack substitution that breaks existing
  implementation contracts.
- MINOR: New principle added, new mandatory section, or material expansion of
  existing guidance.
- PATCH: Clarifications, wording improvements, typo fixes, non-semantic refinements.

**Compliance review**: Every feature plan (`plan.md`) MUST include a "Constitution
Check" gate verifying compliance with Principles I–V before implementation begins.
Violations MUST be documented in the plan's Complexity Tracking table with
justification and simpler alternative considered.

**Version**: 1.0.0 | **Ratified**: 2026-03-22 | **Last Amended**: 2026-03-22
