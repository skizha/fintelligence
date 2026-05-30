"""Validate that citation accession numbers exist in the Elasticsearch index."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from elasticsearch import AsyncElasticsearch

from src.models.schemas import QueryResult

_CITE_RE = re.compile(r"^(.+)_page_(\d+)$")


@dataclass
class CitationIssue:
    cite: str
    issue: str


async def validate_citations(result: QueryResult) -> list[CitationIssue]:
    if not result.companies:
        return []

    url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    issues: list[CitationIssue] = []

    accessions_to_check: dict[str, str] = {}
    for company in result.companies:
        match = _CITE_RE.match(company.cite)
        if not match:
            issues.append(CitationIssue(cite=company.cite, issue="invalid_cite_format"))
            continue
        accession_number = match.group(1)
        accessions_to_check[company.cite] = accession_number

    if not accessions_to_check:
        return issues

    unique_accessions = list(set(accessions_to_check.values()))
    try:
        async with AsyncElasticsearch([url]) as es:
            resp = await es.search(
                index="earnings_chunks",
                body={
                    "query": {"terms": {"accession_number": unique_accessions}},
                    "size": 1,
                    "_source": ["accession_number"],
                    "aggs": {
                        "found_accessions": {
                            "terms": {"field": "accession_number", "size": len(unique_accessions)}
                        }
                    },
                },
            )
        found = {
            bucket["key"]
            for bucket in resp.get("aggregations", {})
            .get("found_accessions", {})
            .get("buckets", [])
        }
    except Exception as exc:
        return issues

    for cite, accession in accessions_to_check.items():
        if accession not in found:
            issues.append(CitationIssue(cite=cite, issue=f"accession_not_found:{accession}"))

    return issues
