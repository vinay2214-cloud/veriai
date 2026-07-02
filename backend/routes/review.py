"""Review Queue API — Human-in-the-Loop.
Manages the review queue for low-trust audit results.
Returns enriched data by cross-referencing the audits table.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from .. import database as db
from .. import config
from ..security.audit_logger import ChainedAuditLogger

router = APIRouter()
logger = logging.getLogger(__name__)
audit_logger = ChainedAuditLogger()


def _apply_rlhf_feedback(audit_id: str, status: str, notes: str):
    weights = dict(config.get_active_weights())
    old_weights = dict(weights)

    delta = 0.05 if status == "approved" else -0.05

    weights["truth"] = max(0.0, weights.get("truth", 0.40) + delta)
    weights["bias"] = max(0.0, weights.get("bias", 0.40) - delta)
    
    total = sum(weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in weights.items()}
        config.CUSTOM_WEIGHTS.clear()
        config.CUSTOM_WEIGHTS.update(new_weights)
        
        audit_logger.append("rlhf_weight_update", {
            "audit_id": audit_id,
            "action": status,
            "notes": notes,
            "old_weights": old_weights,
            "new_weights": new_weights
        })



class ReviewAction(BaseModel):
    notes: Optional[str] = Field("", description="Reviewer notes")


@router.get("/review/queue")
async def get_review_queue():
    """List all reviews enriched with full audit data (scores, correction)."""
    rows = await db.get_pending_reviews(limit=50)
    enriched = []
    for r in rows:
        audit_id = r[1]
        # Cross-reference with audits table for full scores
        audit_row = await db.get_audit(audit_id)
        audit_data = {}
        if audit_row:
            audit_data = {
                "bias_score": audit_row[2],
                "truth_score": audit_row[3],
                "corrected_output": audit_row[5],
            }

        enriched.append({
            "id": r[0],
            "audit_id": audit_id,
            "trust_score": r[2],
            "input_preview": r[3],
            "status": r[4],
            "reviewer_notes": r[5] or "",
            "created_at": r[6],
            "reviewed_at": r[7],
            # Enriched fields from audit
            "bias_score": audit_data.get("bias_score"),
            "truth_score": audit_data.get("truth_score"),
            "corrected_output": audit_data.get("corrected_output"),
        })
    return enriched


@router.get("/review/stats")
async def review_stats():
    """Return pending/approved/rejected counts."""
    try:
        return await db.get_review_stats()
    except Exception:
        return {"pending": 0, "approved": 0, "rejected": 0, "escalated": 0}


async def _require_audit(audit_id: str):
    """404 if the audit does not exist, so we don't silently 'succeed' on bad IDs."""
    audit_row = await db.get_audit(audit_id)
    if not audit_row:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found.")


@router.post("/review/{audit_id}/approve")
async def approve_review(audit_id: str, action: ReviewAction):
    """Approve a flagged audit result."""
    await _require_audit(audit_id)
    try:
        await db.update_review_status(audit_id, "approved", action.notes)
        _apply_rlhf_feedback(audit_id, "approved", action.notes)
    except Exception:
        logger.exception("Failed to approve review %s", audit_id)
        raise HTTPException(status_code=503, detail="Unable to update review right now.")
    return {"status": "success", "message": f"Audit {audit_id} approved.", "audit_id": audit_id}


@router.post("/review/{audit_id}/reject")
async def reject_review(audit_id: str, action: ReviewAction):
    """Reject a flagged audit result with notes."""
    if not action.notes:
        raise HTTPException(status_code=400, detail="Rejection requires reviewer notes.")
    await _require_audit(audit_id)
    try:
        await db.update_review_status(audit_id, "rejected", action.notes)
        _apply_rlhf_feedback(audit_id, "rejected", action.notes)
    except Exception:
        logger.exception("Failed to reject review %s", audit_id)
        raise HTTPException(status_code=503, detail="Unable to update review right now.")
    return {"status": "success", "message": f"Audit {audit_id} rejected.", "audit_id": audit_id}


@router.post("/review/{audit_id}/escalate")
async def escalate_review(audit_id: str, action: ReviewAction):
    """Escalate a flagged audit for further investigation."""
    await _require_audit(audit_id)
    try:
        await db.update_review_status(audit_id, "escalated", action.notes)
    except Exception:
        logger.exception("Failed to escalate review %s", audit_id)
        raise HTTPException(status_code=503, detail="Unable to update review right now.")
    return {"status": "success", "message": f"Audit {audit_id} escalated.", "audit_id": audit_id}
