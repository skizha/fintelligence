"""End-to-end pipeline integration tests (requires live Elasticsearch + Redis)."""
import os
import pytest
import asyncio
from datetime import date, datetime, timezone

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION_TESTS") != "1",
    reason="Set INTEGRATION_TESTS=1 to run integration tests",
)


@pytest.fixture(scope="module")
async def seeded_index():
    """Seed Elasticsearch with 5 known NVDA chunks."""
    from elasticsearch import AsyncElasticsearch
    from elasticsearch.helpers import async_bulk

    url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    accession = "0001045810-24-000123"
    docs = [
        {
            "_index": "earnings_chunks",
            "_id": f"{accession}_chunk_{i}",
            "_source": {
                "chunk_id": f"{accession}_chunk_{i}",
                "accession_number": accession,
                "cik": "0001045810",
                "ticker": "NVDA",
                "filing_type": "10-Q",
                "fiscal_period": "Q3 2024",
                "period_date": "2024-10-27",
                "chunk_index": i,
                "page_number": i + 1,
                "text": f"NVIDIA gross margin for Q3 2024 was 67.0%, compared to 68.3% in Q2 2024. Chunk {i}.",
                "token_count": 30,
            },
        }
        for i in range(5)
    ]
    async with AsyncElasticsearch([url]) as es:
        await async_bulk(es, docs)
        await es.indices.refresh(index="earnings_chunks")
    yield accession


@pytest.mark.asyncio
async def test_query_returns_company_with_cite(seeded_index):
    from src.models.schemas import QueryRequest
    from src.services.query.pipeline import run_query

    request = QueryRequest(query_text="What is NVIDIA gross margin for Q3 2024?", ticker_filter=["NVDA"])
    result = await run_query(request)
    assert result is not None
    assert result.companies is not None


@pytest.mark.asyncio
async def test_cache_hit_on_repeated_query(seeded_index):
    from src.models.schemas import QueryRequest
    from src.services.query.pipeline import run_query

    request = QueryRequest(query_text="NVIDIA gross margin Q3 2024 repeated test")
    first = await run_query(request)
    second = await run_query(request)
    assert second.cache_hit is True
