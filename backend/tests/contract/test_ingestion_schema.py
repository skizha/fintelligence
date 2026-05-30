"""Contract tests for ingestion API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
import uuid

from src.api.main import app
from src.models.schemas import IngestionReport


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _mock_report(run_id: str) -> IngestionReport:
    return IngestionReport(
        run_id=run_id,
        ticker="NVDA",
        triggered_by="api",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        filings_fetched=4,
        chunks_indexed=1842,
        filings_skipped=0,
        failures=[],
    )


def test_post_ingest_returns_202_with_run_id(client):
    resp = client.post("/api/v1/ingest", json={"ticker": "NVDA"})
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert data["triggered_by"] == "api"


def test_get_ingest_run_id_returns_report(client):
    post_resp = client.post("/api/v1/ingest", json={"ticker": "NVDA"})
    run_id = post_resp.json()["run_id"]
    get_resp = client.get(f"/api/v1/ingest/{run_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["run_id"] == run_id
    assert "filings_fetched" in data
    assert "chunks_indexed" in data
    assert "failures" in data


def test_get_ingest_unknown_run_id_returns_404(client):
    resp = client.get(f"/api/v1/ingest/{uuid.uuid4()}")
    assert resp.status_code == 404
