"""Dual indexing: Pinecone (vector) + Elasticsearch (BM25). Atomic per batch."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from elasticsearch import AsyncElasticsearch
from openai import AsyncOpenAI
from pinecone import Pinecone

from src.models.schemas import Chunk, IngestionFailure

_BATCH_SIZE = 100
_ES_INDEX = "earnings_chunks"


async def _embed_batch(texts: list[str], client: AsyncOpenAI) -> list[list[float]]:
    resp = await client.embeddings.create(
        input=texts, model="text-embedding-3-large", dimensions=1536
    )
    return [item.embedding for item in resp.data]


async def _delete_es_chunks(chunk_ids: list[str], es_url: str) -> None:
    """Roll back ES chunks when Pinecone upsert fails."""
    try:
        async with AsyncElasticsearch([es_url]) as es:
            for chunk_id in chunk_ids:
                await es.delete(index=_ES_INDEX, id=chunk_id, ignore=[404])
    except Exception:
        pass


async def index_chunks(chunks: list[Chunk]) -> list[IngestionFailure]:
    if not chunks:
        return []

    openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index_name = os.environ.get("PINECONE_INDEX_NAME", "earnings-chunks")
    pc_index = pc.Index(index_name)
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")

    failures: list[IngestionFailure] = []

    for batch_start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[batch_start : batch_start + _BATCH_SIZE]
        texts = [c.text for c in batch]

        try:
            embeddings = await _embed_batch(texts, openai_client)
        except Exception as exc:
            for c in batch:
                failures.append(IngestionFailure(
                    accession_number=c.accession_number,
                    source_url="",
                    error_type="embedding_error",
                    error_message=str(exc),
                    occurred_at=datetime.now(timezone.utc),
                ))
            continue

        pinecone_vectors = [
            {
                "id": c.chunk_id,
                "values": emb,
                "metadata": {
                    "ticker": c.ticker,
                    "filing_type": c.filing_type,
                    "fiscal_period": c.fiscal_period,
                    "period_date": c.period_date.isoformat(),
                    "accession_number": c.accession_number,
                    "page_number": c.page_number,
                    "cik": c.cik,
                },
            }
            for c, emb in zip(batch, embeddings)
        ]

        es_docs = [
            {"_index": _ES_INDEX, "_id": c.chunk_id, "_source": c.model_dump(mode="json")}
            for c in batch
        ]

        # Pinecone first — if it fails, ES is never written (atomic)
        try:
            pc_index.upsert(vectors=pinecone_vectors)
        except Exception as exc:
            for c in batch:
                failures.append(IngestionFailure(
                    accession_number=c.accession_number,
                    source_url="",
                    error_type="pinecone_error",
                    error_message=str(exc),
                    occurred_at=datetime.now(timezone.utc),
                ))
            continue  # skip ES write for this batch

        # ES second — if it fails, roll back Pinecone vectors
        try:
            from elasticsearch.helpers import async_bulk
            async with AsyncElasticsearch([es_url]) as es:
                await async_bulk(es, es_docs)
        except Exception as exc:
            # Roll back Pinecone
            try:
                pc_index.delete(ids=[v["id"] for v in pinecone_vectors])
            except Exception:
                pass
            for c in batch:
                failures.append(IngestionFailure(
                    accession_number=c.accession_number,
                    source_url="",
                    error_type="elasticsearch_error",
                    error_message=str(exc),
                    occurred_at=datetime.now(timezone.utc),
                ))

    return failures
