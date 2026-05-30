"""Initialize Pinecone serverless index (idempotent)."""
import os

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

load_dotenv()


def init_pinecone_index() -> None:
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index_name = os.environ.get("PINECONE_INDEX_NAME", "earnings-chunks")

    existing = [idx.name for idx in pc.list_indexes()]
    if index_name in existing:
        print(f"Index '{index_name}' already exists — skipping creation.")
        return

    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    print(f"Created Pinecone index '{index_name}' (1536 dims, cosine, us-east-1).")


if __name__ == "__main__":
    init_pinecone_index()
