"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from src.scheduler.ingestion_job import start_scheduler, stop_scheduler

    await start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(
    title="Fintelligence — Earnings Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.routers import health, ingestion, query  # noqa: E402

app.include_router(query.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")

_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
