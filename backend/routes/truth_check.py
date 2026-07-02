"""Standalone truth‑check endpoint.
Verifies claims against the local knowledge base using RAG.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..services.llm_factcheck_service import verify_text_with_llm_rag
from ..services.truth_service import invalidate_cache

router = APIRouter()
logger = logging.getLogger(__name__)


class TruthCheckRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=8000, description="Claim text to verify")


@router.post("/truth-check")
async def truth_check(request: TruthCheckRequest):
    """Verify a single claim against the knowledge base."""
    invalidate_cache()
    try:
        result = await verify_text_with_llm_rag(request.claim)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("truth-check failed")
        raise HTTPException(status_code=502, detail="Truth verification is temporarily unavailable.")
    return result
