"""CLI for on-demand ingestion: python -m src.services.ingestion.cli --ticker NVDA --max-filings 4"""
import argparse
import asyncio
import json
import sys
from datetime import date, datetime

from dotenv import load_dotenv
load_dotenv()


def _serialize(obj: object) -> object:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC EDGAR filings for a ticker.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. NVDA)")
    parser.add_argument("--max-filings", type=int, default=4, help="Max filings per type (default: 4)")
    parser.add_argument("--filing-types", nargs="+", default=["10-K", "10-Q"])
    parser.add_argument("--force", action="store_true", help="Re-ingest even if already indexed")
    args = parser.parse_args()

    from src.services.ingestion.pipeline import run_ingestion

    print(f"Starting ingestion for {args.ticker}…", file=sys.stderr)
    report = await run_ingestion(
        ticker=args.ticker,
        filing_types=args.filing_types,
        max_filings=args.max_filings,
        triggered_by="api",
        force=args.force,
    )
    print(json.dumps(report.model_dump(), indent=2, default=_serialize))


if __name__ == "__main__":
    asyncio.run(main())
