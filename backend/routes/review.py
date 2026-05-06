"""Review Queue API — Human-in-the-Loop.
Manages the review queue for low-trust audit results.
Returns enriched data by cross-referencing the audits table.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from .. import database as db

router = APIRouter()


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


@router.post("/review/{audit_id}/approve")
async def approve_review(audit_id: str, action: ReviewAction):
    """Approve a flagged audit result."""
    await db.update_review_status(audit_id, "approved", action.notes)
    return {"status": "success", "message": f"Audit {audit_id} approved.", "audit_id": audit_id}


@router.post("/review/{audit_id}/reject")
async def reject_review(audit_id: str, action: ReviewAction):
    """Reject a flagged audit result with notes."""
    if not action.notes:
        raise HTTPException(status_code=400, detail="Rejection requires reviewer notes.")
    await db.update_review_status(audit_id, "rejected", action.notes)
    return {"status": "success", "message": f"Audit {audit_id} rejected.", "audit_id": audit_id}


@router.post("/review/{audit_id}/escalate")
async def escalate_review(audit_id: str, action: ReviewAction):
    """Escalate a flagged audit for further investigation."""
    await db.update_review_status(audit_id, "escalated", action.notes)
    return {"status": "success", "message": f"Audit {audit_id} escalated.", "audit_id": audit_id}
