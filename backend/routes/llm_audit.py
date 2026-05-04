from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import database as db
from ..services.llm_audit_service import audit_llm_output

router = APIRouter()


class LLMAuditRequest(BaseModel):
    model_name: str = Field(..., min_length=2, max_length=128)
    prompt: str = Field(..., min_length=3, max_length=8000)
    output_text: str = Field(..., min_length=3, max_length=20000)


@router.post("/audit-llm-output")
async def audit_llm_endpoint(request: LLMAuditRequest):
    try:
        result = await audit_llm_output(
            prompt=request.prompt.strip(),
            output_text=request.output_text.strip(),
            model_name=request.model_name.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.insert_audit(
        audit_id=result["audit_id"],
        input_text=result["input_text"],
        bias_score=result["bias"]["bias_score"],
        truth_score=result["truth"]["truth_score"],
        trust_score=result["trust_score"],
        corrected=result.get("corrections", ""),
        audit_type="llm",
        model_name=result.get("model_name"),
        prompt=result.get("prompt"),
        report_json=result,
    )

    if result.get("requires_human_review"):
        await db.insert_review(
            audit_id=result["audit_id"],
            trust_score=result["trust_score"],
            input_preview=result["input_text"][:200],
        )
    return result
