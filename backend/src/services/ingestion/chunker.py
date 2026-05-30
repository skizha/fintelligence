"""Fixed 512-token chunking with 50-token overlap using tiktoken cl100k_base."""
from __future__ import annotations

from datetime import date

import tiktoken

from src.models.schemas import Chunk

_ENCODING = tiktoken.get_encoding("cl100k_base")
_CHUNK_SIZE = 512
_OVERLAP = 50
_AVG_CHARS_PER_PAGE = 3000


def chunk_document(
    text: str,
    accession_number: str,
    metadata: dict,
) -> list[Chunk]:
    tokens = _ENCODING.encode(text)
    chunks: list[Chunk] = []
    index = 0
    start = 0

    while start < len(tokens):
        end = min(start + _CHUNK_SIZE, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = _ENCODING.decode(chunk_tokens)

        char_offset = len(_ENCODING.decode(tokens[:start]))
        page_number = max(1, (char_offset // _AVG_CHARS_PER_PAGE) + 1)
        token_count = len(chunk_tokens)

        period_date = metadata.get("period_date")
        if isinstance(period_date, str):
            period_date = date.fromisoformat(period_date)

        chunk = Chunk(
            chunk_id=f"{accession_number}_chunk_{index}",
            accession_number=accession_number,
            cik=metadata.get("cik", ""),
            ticker=metadata.get("ticker", ""),
            filing_type=metadata.get("filing_type", ""),
            fiscal_period=metadata.get("fiscal_period", ""),
            period_date=period_date or date.today(),
            chunk_index=index,
            page_number=page_number,
            text=chunk_text,
            token_count=token_count,
        )
        chunks.append(chunk)

        start += _CHUNK_SIZE - _OVERLAP
        index += 1

    return chunks
