"""Latency benchmark: p95 < 1s cached, < 10s uncached.

Usage:
  python -m tests.benchmarks.query_latency --queries 20 --mode cached
  python -m tests.benchmarks.query_latency --queries 20 --mode uncached
"""
import argparse
import asyncio
import statistics
import sys
import time
import uuid


async def run_benchmark(n_queries: int, mode: str) -> None:
    from src.models.schemas import QueryRequest
    from src.services.cache.query_cache import build_cache_key
    import redis.asyncio as aioredis
    import os

    if mode == "cached":
        query_text = "What is NVIDIA gross margin for Q3 2024? [benchmark]"
        queries = [QueryRequest(query_text=query_text)] * n_queries
    else:
        queries = [
            QueryRequest(query_text=f"Benchmark query {uuid.uuid4()} fiscal data?")
            for _ in range(n_queries)
        ]
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url)
        for q in queries:
            key = build_cache_key(q.query_text, q.fiscal_period_filter, q.ticker_filter)
            await r.delete(key)
        await r.aclose()

    from src.services.query.pipeline import run_query

    latencies: list[float] = []
    for i, q in enumerate(queries):
        start = time.monotonic()
        try:
            await run_query(q)
        except Exception as exc:
            print(f"  Query {i+1} failed: {exc}", file=sys.stderr)
        elapsed = (time.monotonic() - start) * 1000
        latencies.append(elapsed)
        print(f"  Query {i+1:3d}: {elapsed:.0f}ms")

    if not latencies:
        print("No successful queries.", file=sys.stderr)
        sys.exit(1)

    latencies.sort()
    p50 = statistics.median(latencies)
    p95_idx = max(0, int(len(latencies) * 0.95) - 1)
    p95 = latencies[p95_idx]
    avg = statistics.mean(latencies)

    print(f"\n{'='*40}")
    print(f"Mode:    {mode}")
    print(f"Queries: {len(latencies)}")
    print(f"Avg:     {avg:.0f}ms")
    print(f"p50:     {p50:.0f}ms")
    print(f"p95:     {p95:.0f}ms")

    threshold = 1000 if mode == "cached" else 10000
    if p95 > threshold:
        print(f"FAIL: p95 {p95:.0f}ms exceeds {threshold}ms target")
        sys.exit(1)
    else:
        print(f"PASS: p95 {p95:.0f}ms <= {threshold}ms target")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--mode", choices=["cached", "uncached"], required=True)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.queries, args.mode))


if __name__ == "__main__":
    main()
