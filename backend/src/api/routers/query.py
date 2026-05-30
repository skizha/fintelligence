"""POST /api/v1/query endpoint."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.models.schemas import QueryRequest, QueryResult
from src.services.query.llm_generator import LLMValidationError
from src.services.query.pipeline import run_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResult)
async def query_endpoint(request: QueryRequest) -> QueryResult | JSONResponse:
    try:
        return await run_query(request)
    except LLMValidationError as exc:
        return JSONResponse(
            status_code=500,
            content={"error": "upstream_validation_failure", "message": str(exc)},
        )
    except Exception as exc:
        if "retrieval" in str(exc).lower() or "pinecone" in str(exc).lower() or "elasticsearch" in str(exc).lower():
            return JSONResponse(
                status_code=503,
                content={"error": "retrieval_unavailable", "message": str(exc)},
            )
        raise
