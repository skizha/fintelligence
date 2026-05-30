"""Sparse BM25 retrieval via Elasticsearch."""
from __future__ import annotations

import os
from dataclasses import dataclass

from elasticsearch import AsyncElasticsearch

from src.services.retrieval.pinecone_retriever import ScoredChunk

INDEX_NAME = "earnings_chunks"


def _get_es() -> AsyncElasticsearch:
    url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    return AsyncElasticsearch([url])


async def retrieve_sparse(
    query_text: str,
    filters: dict | None = None,
    top_k: int = 50,
) -> list[ScoredChunk]:
    must_clauses: list[dict] = [{"match": {"text": {"query": query_text, "analyzer": "english"}}}]
    filter_clauses: list[dict] = []

    if filters:
        if filters.get("ticker_filter"):
            filter_clauses.append({"terms": {"ticker": filters["ticker_filter"]}})
        if filters.get("fiscal_period_filter"):
            filter_clauses.append({"term": {"fiscal_period": filters["fiscal_period_filter"]}})

    query: dict = {"bool": {"must": must_clauses}}
    if filter_clauses:
        query["bool"]["filter"] = filter_clauses

    async with _get_es() as es:
        resp = await es.search(
            index=INDEX_NAME,
            body={"query": query, "size": top_k, "_source": ["chunk_id", "ticker", "fiscal_period", "accession_number", "page_number"]},
        )

    hits = resp["hits"]["hits"]
    return [
        ScoredChunk(
            chunk_id=hit["_id"],
            score=hit["_score"],
            metadata=hit.get("_source", {}),
        )
        for hit in hits
    ]
