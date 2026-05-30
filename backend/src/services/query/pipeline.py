"""Query pipeline: cache → dense+sparse retrieval → RRF → rerank → generate → cache."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from src.models.schemas import QueryRequest, QueryResult
from src.services.cache import query_cache
from src.services.query.citation_validator import validate_citations
from src.services.query.llm_generator import LLMValidationError, generate
from src.services.query.query_logger import write_query_log
from src.services.retrieval.cohere_reranker import rerank
from src.services.retrieval.es_retriever import retrieve_sparse
from src.services.retrieval.pinecone_retriever import retrieve_dense
from src.services.retrieval.rrf_fusion import fuse_rrf


async def _fetch_chunk_texts(chunk_ids: list[str]) -> dict[str, str]:
    """Retrieve chunk texts from Elasticsearch by chunk_id."""
    from elasticsearch import AsyncElasticsearch
    import os

    url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    async with AsyncElasticsearch([url]) as es:
        resp = await es.search(
            index="earnings_chunks",
            body={
                "query": {"ids": {"values": chunk_ids}},
                "size": len(chunk_ids),
                "_source": ["text", "accession_number", "page_number"],
            },
        )
    return {
        hit["_id"]: hit["_source"].get("text", "")
        for hit in resp["hits"]["hits"]
    }


async def run_query(request: QueryRequest) -> QueryResult:
    start = time.monotonic()

    filters = {
        "ticker_filter": request.ticker_filter,
        "fiscal_period_filter": request.fiscal_period_filter,
    }

    cache_key = query_cache.build_cache_key(
        request.query_text,
        request.fiscal_period_filter,
        request.ticker_filter,
    )

    cached = await query_cache.get(cache_key)
    if cached is not None:
        cached.cache_hit = True
        latency_ms = int((time.monotonic() - start) * 1000)
        write_query_log(
            query_request=request,
            result=cached,
            pinecone_scores=[],
            es_scores=[],
            reranker_scores=[],
            latency_ms=latency_ms,
        )
        return cached

    dense_task = asyncio.create_task(retrieve_dense(request.query_text, filters))
    sparse_task = asyncio.create_task(retrieve_sparse(request.query_text, filters))
    dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)

    pinecone_scores = [c.score for c in dense_results]
    es_scores = [c.score for c in sparse_results]

    fused_ids = fuse_rrf(dense_results, sparse_results, k=60)

    chunk_texts = await _fetch_chunk_texts(fused_ids)
    ordered_texts = [chunk_texts.get(cid, "") for cid in fused_ids]

    ranked_chunks = await rerank(request.query_text, fused_ids, ordered_texts)
    reranker_scores = [c.reranker_score for c in ranked_chunks]

    result = await generate(request.query_text, ranked_chunks)
    result.cache_hit = False

    # Drop entries with null/malformed citations
    citation_issues = await validate_citations(result)
    bad_cites = {issue.cite for issue in citation_issues}
    if bad_cites:
        result.companies = [c for c in result.companies if c.cite not in bad_cites]

    if len(result.companies) > 20:
        result.companies = result.companies[:20]
        result.truncated = True

    await query_cache.set(cache_key, result)

    latency_ms = int((time.monotonic() - start) * 1000)
    write_query_log(
        query_request=request,
        result=result,
        pinecone_scores=pinecone_scores,
        es_scores=es_scores,
        reranker_scores=reranker_scores,
        latency_ms=latency_ms,
    )

    return result
