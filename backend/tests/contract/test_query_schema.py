"""Contract tests for POST /api/v1/query."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.api.main import app
from src.models.schemas import CompanyResult, QueryResult


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _mock_result(cache_hit: bool = False) -> QueryResult:
    return QueryResult(
        query_text="What is NVIDIA gross margin?",
        companies=[
            CompanyResult(
                name="NVIDIA Corporation",
                ticker="NVDA",
                metric_name="gross_margin",
                prior_value=0.683,
                current_value=0.670,
                change=-0.013,
                unit="ratio",
                cite="0001045810-24-000123_page_42",
            )
        ],
        truncated=False,
        explanation=None,
        generated_at=datetime.now(timezone.utc),
        cache_hit=cache_hit,
    )


@patch("src.services.query.pipeline.run_query", new_callable=AsyncMock)
def test_query_returns_valid_schema(mock_run_query, client):
    mock_run_query.return_value = _mock_result()
    resp = client.post("/api/v1/query", json={"query_text": "What is NVIDIA gross margin?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "companies" in data
    assert "truncated" in data
    assert "cache_hit" in data
    assert "generated_at" in data


@patch("src.services.query.pipeline.run_query", new_callable=AsyncMock)
def test_every_company_has_cite(mock_run_query, client):
    mock_run_query.return_value = _mock_result()
    resp = client.post("/api/v1/query", json={"query_text": "What is NVIDIA gross margin?"})
    assert resp.status_code == 200
    for company in resp.json()["companies"]:
        assert company["cite"] is not None
        assert "_page_" in company["cite"]


@patch("src.services.query.pipeline.run_query", new_callable=AsyncMock)
def test_truncated_always_present(mock_run_query, client):
    mock_run_query.return_value = _mock_result()
    resp = client.post("/api/v1/query", json={"query_text": "test"})
    assert resp.status_code == 200
    assert "truncated" in resp.json()


def test_missing_query_text_returns_422(client):
    resp = client.post("/api/v1/query", json={})
    assert resp.status_code == 422
