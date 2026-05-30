"""GPT-4 Turbo LLM generation with mandatory Pydantic validation."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from openai import AsyncOpenAI
from pydantic import ValidationError

from src.models.schemas import CompanyResult, QueryResult
from src.services.retrieval.cohere_reranker import RankedChunk

MODEL = "gpt-4-turbo-2024-04-09"

_SYSTEM_PROMPT = """You are a financial data extraction assistant. Given a set of SEC filing excerpts and a user query, extract only financial figures that are explicitly present in the provided text chunks.

For each relevant company, return a JSON object with:
- name: company name from the filing
- ticker: ticker symbol
- metric_name: the specific financial metric (e.g., "gross_margin", "revenue")
- prior_value: prior period value (null if not stated)
- current_value: current or guidance value (null if not stated)
- change: current_value - prior_value (null if either is absent)
- unit: unit of measurement (e.g., "ratio", "USD_millions")
- cite: citation in format "{accession_number}_page_{page_number}"

CRITICAL RULES:
1. Only cite figures that are EXPLICITLY in the provided chunks — never hallucinate.
2. cite MUST always be present. If you cannot identify the source, omit the company entirely.
3. Return at most 20 companies.
4. If no relevant data is found, return an empty companies array with an explanation.

Return valid JSON matching this schema:
{
  "companies": [...],
  "truncated": false,
  "explanation": null or string
}"""


class LLMValidationError(Exception):
    pass


_client: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


async def generate(query_text: str, ranked_chunks: list[RankedChunk]) -> QueryResult:
    chunks_context = "\n\n".join(
        f"[Chunk ID: {c.chunk_id}]\n{c.text}" for c in ranked_chunks
    )
    user_message = f"Query: {query_text}\n\nRelevant filing excerpts:\n{chunks_context}"

    client = _get_openai()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = response.choices[0].message.content
    if not raw:
        raise LLMValidationError("LLM returned empty response")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMValidationError(f"LLM response is not valid JSON: {exc}") from exc

    companies_raw = data.get("companies", [])
    companies: list[CompanyResult] = []
    for entry in companies_raw:
        try:
            companies.append(CompanyResult.model_validate(entry))
        except ValidationError:
            # Drop entries that fail validation (no cite, malformed fields)
            continue

    truncated = data.get("truncated", False)
    explanation = data.get("explanation")

    if len(companies) > 20:
        companies = companies[:20]
        truncated = True

    try:
        result = QueryResult(
            query_text=query_text,
            companies=companies,
            truncated=truncated,
            explanation=explanation,
            generated_at=datetime.now(timezone.utc),
            cache_hit=False,
        )
    except ValidationError as exc:
        raise LLMValidationError(f"QueryResult validation failed: {exc}") from exc

    return result
