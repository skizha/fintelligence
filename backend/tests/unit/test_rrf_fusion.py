"""Unit tests for Reciprocal Rank Fusion."""
import pytest

from src.services.retrieval.pinecone_retriever import ScoredChunk
from src.services.retrieval.rrf_fusion import fuse_rrf


def _make_chunks(ids: list[str], base_score: float = 1.0) -> list[ScoredChunk]:
    return [ScoredChunk(chunk_id=cid, score=base_score - i * 0.01, metadata={}) for i, cid in enumerate(ids)]


def test_rrf_merges_overlapping_results():
    dense = _make_chunks(["a", "b", "c"])
    sparse = _make_chunks(["b", "c", "d"])
    result = fuse_rrf(dense, sparse, k=60)
    assert "a" in result
    assert "b" in result
    assert "c" in result
    assert "d" in result


def test_rrf_output_length_le_50():
    dense = _make_chunks([f"d{i}" for i in range(50)])
    sparse = _make_chunks([f"s{i}" for i in range(50)])
    result = fuse_rrf(dense, sparse, k=60)
    assert len(result) <= 50


def test_rrf_items_ranked_in_both_lists_score_higher():
    shared = ["shared_a", "shared_b"]
    dense_only = ["dense_1", "dense_2", "dense_3"]
    sparse_only = ["sparse_1", "sparse_2", "sparse_3"]
    dense = _make_chunks(shared + dense_only)
    sparse = _make_chunks(shared + sparse_only)
    result = fuse_rrf(dense, sparse, k=60)
    shared_positions = [result.index(s) for s in shared if s in result]
    dense_only_positions = [result.index(d) for d in dense_only if d in result]
    if shared_positions and dense_only_positions:
        assert min(shared_positions) < max(dense_only_positions)


def test_rrf_disjoint_results_merged():
    dense = _make_chunks(["a", "b"])
    sparse = _make_chunks(["c", "d"])
    result = fuse_rrf(dense, sparse, k=60)
    assert set(result) == {"a", "b", "c", "d"}


def test_rrf_empty_inputs():
    result = fuse_rrf([], [], k=60)
    assert result == []


def test_rrf_k60_formula():
    dense = _make_chunks(["x"])
    sparse = _make_chunks(["x"])
    result = fuse_rrf(dense, sparse, k=60)
    assert result[0] == "x"
