"""Dense vector retrieval via Pinecone."""
from __future__ import annotations

import os
from dataclasses import dataclass

from openai import AsyncOpenAI
from pinecone import Pinecone


@dataclass
class ScoredChunk:
    chunk_id: str
    score: float
    metadata: dict


_openai: AsyncOpenAI | None = None
_pc: Pinecone | None = None


def _get_pinecone() -> Pinecone:
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    return _pc


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai


async def retrieve_dense(
    query_text: str,
    filters: dict | None = None,
    top_k: int = 50,
) -> list[ScoredChunk]:
    client = _get_openai()
    response = await client.embeddings.create(
        input=query_text,
        model="text-embedding-3-large",
        dimensions=1536,
    )
    vector = response.data[0].embedding

    pc = _get_pinecone()
    index_name = os.environ.get("PINECONE_INDEX_NAME", "earnings-chunks")
    index = pc.Index(index_name)

    pinecone_filter: dict | None = None
    if filters:
        pinecone_filter = {}
        if filters.get("ticker_filter"):
            pinecone_filter["ticker"] = {"$in": filters["ticker_filter"]}
        if filters.get("fiscal_period_filter"):
            pinecone_filter["fiscal_period"] = {"$eq": filters["fiscal_period_filter"]}

    results = index.query(
        vector=vector,
        top_k=top_k,
        filter=pinecone_filter or None,
        include_metadata=True,
    )

    return [
        ScoredChunk(
            chunk_id=match.id,
            score=match.score,
            metadata=match.metadata or {},
        )
        for match in results.matches
    ]
