"""Redis query response cache with SHA-256 keying."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

import redis.asyncio as aioredis

from src.models.schemas import QueryResult

_TTL_SECONDS = 3600
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis = aioredis.from_url(url, decode_responses=True)
    return _redis


def build_cache_key(query_text: str, fiscal_period_filter: str | None, ticker_filter: list[str] | None) -> str:
    normalized = query_text.strip().lower()
    period = fiscal_period_filter or ""
    tickers = "|".join(sorted(ticker_filter or []))
    raw = f"{normalized}::{period}::{tickers}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _serialize_dt(obj: object) -> object:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


async def get(cache_key: str) -> QueryResult | None:
    client = _get_redis()
    data = await client.get(cache_key)
    if data is None:
        return None
    return QueryResult.model_validate_json(data)


async def set(cache_key: str, result: QueryResult, ttl: int = _TTL_SECONDS) -> None:
    client = _get_redis()
    await client.setex(cache_key, ttl, result.model_dump_json())
