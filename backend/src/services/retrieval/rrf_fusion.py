"""Reciprocal Rank Fusion for merging dense and sparse retrieval results."""
from __future__ import annotations

from src.services.retrieval.pinecone_retriever import ScoredChunk


def fuse_rrf(
    dense_results: list[ScoredChunk],
    sparse_results: list[ScoredChunk],
    k: int = 60,
    top_n: int = 50,
) -> list[str]:
    scores: dict[str, float] = {}

    for rank, chunk in enumerate(dense_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, chunk in enumerate(sparse_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk_id for chunk_id, _ in ranked[:top_n]]
