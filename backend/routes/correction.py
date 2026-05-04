"""Correction endpoint.
Re‑runs the correction engine on a previous audit or on new input.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..services.correction_service import apply_corrections
from ..services.truth_service import verify_claims
from .. import database as db

router = APIRouter()


class CorrectionRequest(BaseModel):
    audit_id: str = Field(None, description="ID of a previous audit to correct")
    input_text: str = Field(None, description="Raw text to correct (if no audit_id)")


@router.post("/correct")
async def correct(request: CorrectionRequest):
    """Apply corrections to an audit or raw input."""
    if request.audit_id:
        row = await db.get_audit(request.audit_id)
        if not row:
            return {"error": "Audit not found"}
        input_text = row[1]  # input column
    elif request.input_text:
        input_text = request.input_text
    else:
        return {"error": "Provide either audit_id or input_text"}

    truth_result = await verify_claims(input_text)
    raw = {
        "input_text": input_text,
        "bias": {"feature_importance": {}},
        "truth": truth_result,
    }
    corrections = apply_corrections(raw)
    return {
        "original": input_text,
        "corrected": corrections.get("truth_corrections", input_text),
        "actions": corrections.get("actions", []),
        "bias_corrections": corrections.get("bias_corrections", {}),
    }
