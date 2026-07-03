"""AI intelligence endpoints (Phase 3).

Additive router that exposes the deterministic AI layer — orchestrator, compliance
officer, review manager, and executive insights. These are all NEW paths under
``/api/ai/*`` and ``/api/insights/*``; no existing endpoint is modified or removed.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import database as db
from ..services import ai_orchestrator, compliance_officer, review_manager, business_metrics

router = APIRouter()
logger = logging.getLogger(__name__)


class SchemaPayload(BaseModel):
    """Inferred dataset schema (the response body of /api/audit/preview-csv)."""
    columns: list = Field(default_factory=list)
    row_count: int = 0
    # tolerate extra keys (preview_rows etc.) without failing validation
    model_config = {"extra": "allow"}


@router.post("/ai/recommend-profile")
async def recommend_profile(payload: SchemaPayload) -> Dict[str, Any]:
    """AI Audit Orchestrator — recommend an audit configuration from a dataset schema."""
    schema = payload.model_dump()
    try:
        return ai_orchestrator.recommend_audit_profile(schema)
    except Exception:
        logger.exception("recommend_profile failed")
        # Safe, neutral fallback so the upload flow never blocks on the recommendation.
        return {
            "audit_profile": "General Trust Audit",
            "depth": "standard",
            "compliance_profile": "general",
            "explainability_level": "standard",
            "review_priority": "standard",
            "report_detail": "standard",
            "detected_protected_attributes": [],
            "detected_domain": "general",
            "rationale": ["Using safe defaults (automatic recommendation unavailable)."],
            "engine": "deterministic",
            "summary": "AI recommends a general trust audit at standard depth.",
        }


async def _load_audit_record(audit_id: str) -> Dict[str, Any]:
    """Reconstruct an audit dict from storage (scores + nested report)."""
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found.")
    import json
    report_json = None
    if len(row) > 9 and row[9]:
        try:
            report_json = json.loads(row[9])
        except Exception:
            report_json = None
    return {
        "audit_id": row[0],
        "audit_type": row[6] if len(row) > 6 else "dataset",
        "bias_score": row[2],
        "truth_score": row[3],
        "trust_score": row[4],
        "report": report_json or {},
    }


@router.get("/ai/compliance-report/{audit_id}")
async def compliance_report(audit_id: str, llm_polish: bool = Query(False)) -> Dict[str, Any]:
    """AI Compliance Officer — consultant-grade narrative for a stored audit."""
    audit = await _load_audit_record(audit_id)
    summary = compliance_officer.summarize(audit, llm_polish=llm_polish)
    return {"audit_id": audit_id, "compliance": summary}


async def _enriched_queue() -> list:
    """Rebuild the review queue with the scores the review manager needs."""
    rows = await db.get_pending_reviews(limit=50)
    items = []
    for r in rows:
        audit_id = r[1]
        audit_row = await db.get_audit(audit_id)
        bias_score = audit_row[2] if audit_row else None
        truth_score = audit_row[3] if audit_row else None
        items.append({
            "id": r[0],
            "audit_id": audit_id,
            "trust_score": r[2],
            "input_preview": r[3],
            "status": r[4],
            "reviewer_notes": r[5] or "",
            "created_at": r[6],
            "reviewed_at": r[7],
            "bias_score": bias_score,
            "truth_score": truth_score,
        })
    return items


@router.get("/ai/review-insights")
async def review_insights() -> Dict[str, Any]:
    """AI Review Manager — prioritized, enriched review queue + roll-up summary."""
    try:
        items = await _enriched_queue()
    except Exception:
        logger.exception("review_insights queue build failed")
        items = []
    prioritized = review_manager.prioritize(items)
    return {
        "queue": prioritized,
        "summary": review_manager.queue_summary(prioritized),
    }


@router.get("/insights/executive")
async def executive_insights() -> Dict[str, Any]:
    """Executive business-intelligence dashboard payload."""
    return await business_metrics.executive_insights()
