"""Initialize Elasticsearch index for BM25 keyword search (idempotent)."""
import asyncio
import os

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

load_dotenv()

INDEX_NAME = "earnings_chunks"

MAPPING = {
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "accession_number": {"type": "keyword"},
            "cik": {"type": "keyword"},
            "ticker": {"type": "keyword"},
            "filing_type": {"type": "keyword"},
            "fiscal_period": {"type": "keyword"},
            "period_date": {"type": "date"},
            "chunk_index": {"type": "integer"},
            "page_number": {"type": "integer"},
            "text": {"type": "text", "analyzer": "english"},
            "token_count": {"type": "integer"},
        }
    }
}


async def init_es_index() -> None:
    url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    async with AsyncElasticsearch([url]) as es:
        if await es.indices.exists(index=INDEX_NAME):
            print(f"Index '{INDEX_NAME}' already exists — skipping creation.")
            return
        await es.indices.create(index=INDEX_NAME, body=MAPPING)
        print(f"Created Elasticsearch index '{INDEX_NAME}'.")


if __name__ == "__main__":
    asyncio.run(init_es_index())
