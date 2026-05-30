"""Unit tests for the document chunker."""
import pytest
from datetime import date

from src.services.ingestion.chunker import chunk_document, _ENCODING, _CHUNK_SIZE, _OVERLAP


_ACCESSION = "0001045810-24-000123"
_METADATA = {
    "cik": "0001045810",
    "ticker": "NVDA",
    "filing_type": "10-Q",
    "fiscal_period": "Q3 2024",
    "period_date": date(2024, 10, 27),
}


def _make_text(target_tokens: int) -> str:
    word = "financials "
    token_count = 0
    words = []
    while token_count < target_tokens:
        words.append(word)
        token_count = len(_ENCODING.encode("".join(words)))
    return "".join(words)


def test_chunk_token_count_le_512():
    text = _make_text(2000)
    chunks = chunk_document(text, _ACCESSION, _METADATA)
    for chunk in chunks:
        assert chunk.token_count <= 512


def test_chunk_id_format():
    text = _make_text(600)
    chunks = chunk_document(text, _ACCESSION, _METADATA)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"{_ACCESSION}_chunk_{i}"


def test_page_number_ge_1():
    text = _make_text(1000)
    chunks = chunk_document(text, _ACCESSION, _METADATA)
    for chunk in chunks:
        assert chunk.page_number >= 1


def test_overlap_produces_shared_tokens():
    text = _make_text(1100)
    chunks = chunk_document(text, _ACCESSION, _METADATA)
    if len(chunks) >= 2:
        tokens_0 = set(_ENCODING.encode(chunks[0].text))
        tokens_1 = set(_ENCODING.encode(chunks[1].text))
        overlap = tokens_0 & tokens_1
        assert len(overlap) > 0, "Overlapping chunks should share tokens"


def test_short_document_produces_one_chunk():
    text = "This is a short document."
    chunks = chunk_document(text, _ACCESSION, _METADATA)
    assert len(chunks) == 1


def test_metadata_propagated():
    text = _make_text(100)
    chunks = chunk_document(text, _ACCESSION, _METADATA)
    for chunk in chunks:
        assert chunk.ticker == "NVDA"
        assert chunk.filing_type == "10-Q"
        assert chunk.fiscal_period == "Q3 2024"
