# Feature Specification: Earnings Intelligence Platform

**Feature Branch**: `001-earnings-intelligence-rag`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "based on the project-spec.md — Earnings Intelligence Platform (Hedge Fund): RAG over earnings documents with hybrid retrieval, reranking, and structured output"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Natural Language Financial Query (Priority: P1)

A hedge fund analyst submits a plain-English question about financial metrics across
multiple companies. The system retrieves the most relevant passages from 10-K, 10-Q,
and earnings call transcripts, reranks them for relevance, and returns a structured
response with specific figures, period comparisons, and source citations — all in
under one second for cached queries.

**Why this priority**: This is the core product value. Every other story depends on
this retrieval-and-response loop being correct and fast. Without it there is no
viable product.

**Independent Test**: Can be tested end-to-end with a single query (e.g., "Which
semiconductor companies are guiding down gross margins?") against a small seeded
corpus and validated by asserting that the JSON response contains company names,
prior/current margin figures, deltas, and citation references.

**Acceptance Scenarios**:

1. **Given** a seeded corpus with at least 3 semiconductor company filings,
   **When** an analyst queries "Which semiconductor companies are guiding down gross margins?",
   **Then** the response lists each company with `prior_margin`, `guidance`, `change`, and `cite` fields,
   and at least one citation matches the seeded document.

2. **Given** a repeated identical query,
   **When** the query is submitted within the cache window,
   **Then** the response is returned in under 1 second.

3. **Given** a query that matches no documents,
   **When** the query is submitted,
   **Then** the response returns an empty results array with a human-readable explanation
   and no hallucinated data.

4. **Given** a query with a date filter (e.g., "Q3 2024 guidance changes"),
   **When** the query is submitted,
   **Then** only documents from the specified fiscal period appear in results.

---

### User Story 2 - Automated Earnings Document Ingestion (Priority: P2)

An operator triggers ingestion of the latest SEC filings for a watchlist of tickers.
The system fetches the documents from SEC EDGAR, chunks and embeds them, indexes
them into both the vector store and the keyword index, and confirms completion with
a structured ingestion report.

**Why this priority**: Without a reliable, auditable ingestion pipeline the query
layer has no corpus. Ingestion is the data foundation but can be validated independently
of the query interface.

**Independent Test**: Trigger ingestion for one ticker, verify the document appears
in the index by running a keyword search for a known phrase from the filing.

**Acceptance Scenarios**:

1. **Given** a valid ticker symbol (e.g., NVDA),
   **When** the operator triggers ingestion,
   **Then** the system fetches the most recent 10-K and 10-Q from SEC EDGAR,
   and returns a report with document count, chunk count, and any failures.

2. **Given** a network failure during SEC EDGAR fetch,
   **When** the ingestion runs,
   **Then** the failure is logged with the source URL and document identifier,
   and no partial documents are indexed.

3. **Given** a document already in the index with the same accession number,
   **When** the same document is re-ingested,
   **Then** the system deduplicates and does not create duplicate index entries.

4. **Given** a successful ingestion run,
   **When** a query using a phrase verbatim from the ingested document is submitted,
   **Then** that document appears in the retrieval results.

---

### User Story 3 - Query Result Citation and Auditability (Priority: P3)

An analyst reviews the sources behind a query result. The system surfaces the exact
document, filing section, and page number for each piece of evidence in the response,
so the analyst can verify figures directly in the original filing.

**Why this priority**: Traceability is required for compliance and analyst trust.
It builds on Story 1 (query) but can be validated as a distinct quality dimension
once basic retrieval is working.

**Independent Test**: Submit a query, take one `cite` field from the response,
navigate to the referenced document page, and confirm the figure in the response
appears verbatim or is directly calculable from the source text.

**Acceptance Scenarios**:

1. **Given** a query response with company entries,
   **When** an analyst inspects the `cite` field,
   **Then** the value is a resolvable reference in the format `{DOCUMENT_ID}_{PAGE}` that
   maps to an accessible filing.

2. **Given** a response citing multiple companies,
   **When** the analyst checks two different citations,
   **Then** each citation points to a distinct source document with the correct filing metadata.

3. **Given** a response where the LLM could not find evidence for a figure,
   **When** the response is returned,
   **Then** the field is omitted or marked as `null` rather than fabricated.

---

### Edge Cases

- What happens when SEC EDGAR is unavailable or rate-limits the ingestion request?
  Ingestion MUST fail with a logged error; no partial data enters the index.
- What happens when a query returns more results than the response schema can hold?
  The response MUST cap results at 20 companies and include a `truncated: true` flag
  when the limit is reached.
- What happens when a filing is in an unexpected format (e.g., image-only PDF)?
  The document MUST be skipped with a logged warning; ingestion of other documents continues.
- What happens when the reranker returns all documents with identical scores?
  The system MUST fall back to retrieval order and surface this in the query log.
- What happens when the structured output schema validation fails on the LLM response?
  The response MUST be rejected; the error is logged; no invalid data is returned to the analyst.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept natural language queries via both a REST API and a
  simple web UI, and return structured JSON responses conforming to a versioned output
  schema. The web UI MUST provide a query input form and render results in a
  human-readable format; the REST API MUST return raw JSON suitable for downstream
  integration.
- **FR-002**: System MUST perform hybrid retrieval combining semantic vector search
  and keyword-based (BM25) search for every production query; neither mode may be
  skipped. BM25 is required for all queries — not limited to structured filters —
  because financial queries rely on exact term matching (tickers, fiscal periods,
  metric names) that vector search alone handles poorly.
- **FR-003**: System MUST apply a reranking step after retrieval fusion before
  generating the final response.
- **FR-004**: Every response object MUST include a `cite` field referencing the
  source document identifier and page number.
- **FR-005**: System MUST ingest SEC EDGAR filings (10-K, 10-Q) for a given ticker
  both on a defined recurring schedule and on manual operator demand. Both paths MUST
  confirm completion with a structured ingestion report. The schedule interval is
  configurable; the default targets quarterly earnings cadence.
- **FR-006**: System MUST deduplicate documents at ingestion time using filing
  accession number as the unique identifier.
- **FR-007**: System MUST log every query execution with: query text, retrieval scores,
  reranker scores, response latency, and the full citation set returned.
- **FR-008**: System MUST log every ingestion run with: source URL, document count,
  chunk count, timestamp, and any per-document failures.
- **FR-009**: System MUST validate all LLM-generated responses against the output
  schema before returning them; invalid responses MUST be rejected and logged.
- **FR-010**: System MUST cache responses to repeated identical queries and serve
  cached results within 1 second.
- **FR-011**: System MUST support date-range filtering on queries to restrict
  retrieval to specific fiscal periods.
- **FR-012**: System MUST NOT store or return Personally Identifiable Information
  in query responses or index entries.

### Key Entities

- **Filing**: A regulatory document (10-K, 10-Q, earnings call transcript) sourced
  from SEC EDGAR. Identified by CIK, accession number, filing type, and period date.
- **Chunk**: A passage extracted from a Filing for indexing. Has a chunk index,
  parent filing reference, and the original text.
- **QueryResult**: A structured response to an analyst query. Contains up to 20
  Company entries, each with financial metrics, period comparisons, and a `cite` field.
  Includes a `truncated` boolean flag indicating whether the result set was capped.
- **Company**: A named entity within a QueryResult. Has ticker, name, financial metric
  values (prior and current period), delta, and source citation.
- **IngestionReport**: Summary of a completed ingestion run. Contains ticker, filing
  count, chunk count, timestamp, and a list of any failed documents with reasons.
- **QueryLog**: Audit record of a query execution. Contains query text, retrieval
  and reranker scores, model identifier, latency, and citations returned.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Analysts can get a structured, cited answer to a financial metric query
  covering 3+ companies in under 1 second for cached queries and under 10 seconds
  for uncached queries.
- **SC-002**: Ingestion of a single company's annual and quarterly filings completes
  without manual intervention and produces a verifiable confirmation report.
- **SC-003**: At least 90% of citations in query responses are traceable to the exact
  filing page stated in the `cite` field, as validated on a held-out evaluation set.
- **SC-004**: Analysts reduce time spent manually reviewing earnings documents for a
  specific financial metric across 10+ companies from hours to under 5 minutes.
- **SC-005**: Zero structured responses with missing or null `cite` fields are returned
  for queries that produce at least one result; citation coverage is 100% on returned results.
- **SC-006**: All query executions and ingestion runs produce audit log entries
  retrievable for at least 90 days.

## Clarifications

### Session 2026-03-22

- Q: Is BM25 keyword search required for all production queries or only specific query types? → A: BM25 required for all production queries — hybrid retrieval mandatory as currently spec'd. Rationale: financial queries depend on exact term matching (tickers, fiscal periods, metric names) that vector search alone cannot reliably handle.
- Q: What is the primary query interface surface for analysts? → A: REST API + simple web UI — basic query form for non-technical analysts alongside the HTTP API.
- Q: How is document ingestion triggered? → A: Scheduled + on-demand — automatic runs on a defined schedule plus manual override per ticker.
- Q: What is the maximum number of companies returned per query response? → A: 20 companies maximum per query response.
- Q: What is the uptime/availability expectation for the platform? → A: Best-effort — no formal uptime SLA at this stage.

## Assumptions

- Earnings call transcript availability via SEC EDGAR or an equivalent regulatory
  source is assumed; if transcripts require a separate data provider, that is a scope
  extension to be addressed in a future feature.
- A holdings watchlist (set of tracked tickers) is maintained externally; ingestion
  runs on a configurable schedule (defaulting to quarterly cadence) and can also be
  triggered manually per ticker.
- End users are authenticated professionals (analysts); user authentication and
  multi-tenancy are out of scope for this feature and assumed to be handled by a
  surrounding platform.
- The corpus at launch targets 50,000+ document chunks; the solution must be designed
  to accommodate this volume from day one.
- No formal uptime SLA is defined at this stage; availability is best-effort. A formal
  SLA may be introduced in a future amendment once operational patterns are established.
