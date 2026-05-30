"""Async SEC EDGAR client with rate limiting and retry logic."""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import date

import httpx

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start_dt}&forms={filing_type}"
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms={filing_type}&hits.hits._source.period_of_report=true"
TICKER_CIK_URL = "https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK={ticker}&type=10-K&dateb=&owner=include&count=10&search_text=&action=getcompany&output=atom"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_RATE_LIMIT = 8  # requests per second
_MIN_INTERVAL = 1.0 / _RATE_LIMIT
_last_request_time: float = 0.0
_rate_lock = asyncio.Lock()


@dataclass
class FilingDocument:
    accession_number: str
    cik: str
    ticker: str
    filing_type: str
    fiscal_period: str
    period_date: date
    filed_date: date
    source_url: str
    text: str


async def _throttled_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    global _last_request_time
    async with _rate_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_request_time)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_time = time.monotonic()

    for attempt in range(3):
        resp = await client.get(url, **kwargs)
        if resp.status_code == 429:
            wait_secs = (2 ** attempt) * 1.0
            await asyncio.sleep(wait_secs)
            continue
        resp.raise_for_status()
        return resp

    raise httpx.HTTPStatusError(
        "Max retries exceeded (429)", request=resp.request, response=resp
    )


async def _get_cik(ticker: str, client: httpx.AsyncClient) -> str:
    resp = await _throttled_get(client, COMPANY_TICKERS_URL)
    data = resp.json()
    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            cik = str(entry["cik_str"]).zfill(10)
            return cik
    raise ValueError(f"CIK not found for ticker '{ticker}'")


async def fetch_filings(
    ticker: str,
    filing_types: list[str] | None = None,
    max_filings: int = 4,
) -> list[FilingDocument]:
    if filing_types is None:
        filing_types = ["10-K", "10-Q"]

    user_agent = os.environ.get("EDGAR_USER_AGENT", "fintelligence dev@example.com")
    headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        cik = await _get_cik(ticker, client)
        cik_padded = cik.zfill(10)

        url = EDGAR_SUBMISSIONS_URL.format(cik=cik_padded)
        resp = await _throttled_get(client, url)
        submissions = resp.json()

        filings_data = submissions.get("filings", {}).get("recent", {})
        forms = filings_data.get("form", [])
        accession_numbers = filings_data.get("accessionNumber", [])
        filed_dates = filings_data.get("filingDate", [])
        period_of_reports = filings_data.get("periodOfReport", [])
        primary_docs = filings_data.get("primaryDocument", [])

        results: list[FilingDocument] = []
        count = 0
        for i, form in enumerate(forms):
            if form not in filing_types:
                continue
            if count >= max_filings:
                break

            accession = accession_numbers[i]
            filed_date_str = filed_dates[i] if i < len(filed_dates) else None
            period_str = period_of_reports[i] if i < len(period_of_reports) else None
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""

            accession_no_dashes = accession.replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes}/{primary_doc}"

            try:
                doc_resp = await _throttled_get(client, doc_url)
                text = doc_resp.text
            except Exception as exc:
                raise RuntimeError(f"Failed to fetch document {doc_url}: {exc}") from exc

            period_date = date.fromisoformat(period_str) if period_str else date.today()
            filed_date = date.fromisoformat(filed_date_str) if filed_date_str else date.today()

            quarter = _period_to_quarter(period_date, form)

            results.append(
                FilingDocument(
                    accession_number=accession,
                    cik=cik_padded,
                    ticker=ticker.upper(),
                    filing_type=form,
                    fiscal_period=quarter,
                    period_date=period_date,
                    filed_date=filed_date,
                    source_url=doc_url,
                    text=text,
                )
            )
            count += 1

    return results


def _period_to_quarter(period_date: date, filing_type: str) -> str:
    if filing_type == "10-K":
        return f"FY {period_date.year}"
    month = period_date.month
    if month <= 3:
        q = "Q1"
    elif month <= 6:
        q = "Q2"
    elif month <= 9:
        q = "Q3"
    else:
        q = "Q4"
    return f"{q} {period_date.year}"
