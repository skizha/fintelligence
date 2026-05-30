"""GET /api/v1/health — dependency liveness check."""
from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


async def _check_pinecone() -> str:
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        pc.list_indexes()
        return "ok"
    except Exception:
        return "degraded"


async def _check_elasticsearch() -> str:
    try:
        from elasticsearch import AsyncElasticsearch
        url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        async with AsyncElasticsearch([url]) as es:
            await es.ping()
        return "ok"
    except Exception:
        return "degraded"


async def _check_redis() -> str:
    try:
        import redis.asyncio as aioredis
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(url)
        await r.ping()
        await r.aclose()
        return "ok"
    except Exception:
        return "degraded"


async def _check_openai() -> str:
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        await client.models.list()
        return "ok"
    except Exception:
        return "degraded"


async def _check_cohere() -> str:
    try:
        import cohere
        client = cohere.AsyncClient(api_key=os.environ["COHERE_API_KEY"])
        await client.check_api_key()
        return "ok"
    except Exception:
        return "degraded"


@router.get("/health")
async def health_check() -> JSONResponse:
    import asyncio

    pinecone, elasticsearch, redis, openai, cohere = await asyncio.gather(
        _check_pinecone(),
        _check_elasticsearch(),
        _check_redis(),
        _check_openai(),
        _check_cohere(),
    )

    deps = {
        "pinecone": pinecone,
        "elasticsearch": elasticsearch,
        "redis": redis,
        "openai": openai,
        "cohere": cohere,
    }
    overall = "ok" if all(v == "ok" for v in deps.values()) else "degraded"
    return JSONResponse(content={"status": overall, "dependencies": deps})
