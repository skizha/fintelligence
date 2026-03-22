## Project 1: Production RAG — Financial Intelligence

### 1A. Earnings Intelligence Platform (Hedge Fund)

**Problem:** Analyze 500+ earnings calls quarterly manually = 20 hours per analyst per quarter. Miss guidance changes and competitive signals.

**Solution:** RAG over earnings documents
```
Query: "Which semiconductor companies are guiding down gross margins?"
    ↓
Hybrid Retrieval:
  • Vector: Semantic search on "gross margin guidance"
  • BM25: Keyword matching + date filters
    ↓
Reranking: Cohere Rerank (financial documents)
    ↓
Structured Response:
  {
    "companies": [
      {
        "name": "NVIDIA",
        "prior_margin": 0.683,
        "guidance": 0.67,
        "change": -1.3,
        "cite": "NVIDIA_10-Q_page_42"
      }
    ]
  }
```

**Tech Stack:**
- Data: SEC EDGAR API (auto-fetch 10-K, 10-Q, earnings calls)
- Vector DB: Pinecone (50K+ documents)
- Embeddings: OpenAI text-embedding-3-large
- Sparse: Elasticsearch + BM25
- Reranking: Cohere Rerank (financial-tuned)
- LLM: GPT-4 Turbo + Pydantic structured output
- Backend: FastAPI (sub-1s cached queries)
