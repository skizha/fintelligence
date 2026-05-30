"""Cohere reranking for top-10 chunk selection."""
from __future__ import annotations

import os
from dataclasses import dataclass

import cohere


@dataclass
class RankedChunk:
    chunk_id: str
    reranker_score: float
    text: str


_client: cohere.AsyncClient | None = None


def _get_cohere() -> cohere.AsyncClient:
    global _client
    if _client is None:
        _client = cohere.AsyncClient(api_key=os.environ["COHERE_API_KEY"])
    return _client


async def rerank(
    query_text: str,
    chunk_ids: list[str],
    chunks_text: list[str],
    top_n: int = 10,
) -> list[RankedChunk]:
    if not chunk_ids:
        return []

    client = _get_cohere()
    response = await client.rerank(
        model="rerank-english-v3.0",
        query=query_text,
        documents=chunks_text,
        top_n=min(top_n, len(chunks_text)),
        max_chunks_per_doc=1,
    )

    results: list[RankedChunk] = []
    for result in response.results:
        idx = result.index
        results.append(
            RankedChunk(
                chunk_id=chunk_ids[idx],
                reranker_score=result.relevance_score,
                text=chunks_text[idx],
            )
        )
    return results
