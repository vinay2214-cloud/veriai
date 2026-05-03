"""Full audit endpoints, including mapped CSV ingestion."""
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from ..models import AuditRequest
from ..services.reasoning_chain import run_audit
from ..services.truth_service import invalidate_cache
from ..services.csv_mapping_service import read_csv_bytes, infer_csv_schema, build_mapped_dataset
from .. import database as db

router = APIRouter()


@router.post("/audit")
async def audit(request: AuditRequest):
    """Run the full multi-step audit pipeline with parallel processing."""
    # Invalidate truth cache to pick up any new KB entries
    invalidate_cache()

    try:
        result = await run_audit(
            input_text=request.input_text,
            num_clusters=request.num_clusters,
            depth=request.depth or "standard",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist to SQLite
    await db.insert_audit(
        audit_id=result["audit_id"],
        input_text=result["input_text"],
        bias_score=result["bias"]["bias_score"],
        truth_score=result["truth"]["truth_score"],
        trust_score=result["trust_score"],
        corrected=result.get("corrections", ""),
        audit_type=result.get("audit_type", "dataset"),
        report_json=result,
    )

    # If flagged for human review, add to review queue
    if result.get("requires_human_review"):
        await db.insert_review(
            audit_id=result["audit_id"],
            trust_score=result["trust_score"],
            input_preview=result["input_text"][:200],
        )

    return result


@router.post("/audit/preview-csv")
async def preview_csv(file: UploadFile = File(...)):
    """Preview CSV columns + inferred types/roles before running an audit."""
    content = await file.read()
    try:
        df = read_csv_bytes(content)
        if df.empty:
            raise ValueError("Uploaded CSV is empty.")
        return infer_csv_schema(df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")


@router.post("/audit/run-mapped")
async def run_mapped_audit(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    num_clusters: Optional[int] = Form(None),
    depth: Optional[str] = Form("standard"),
):
    """Run audit from a raw CSV + user-provided column mapping."""
    content = await file.read()
    try:
        mapping_payload = json.loads(mapping)
        if not isinstance(mapping_payload, dict):
            raise ValueError("Mapping must be a JSON object.")
        df = read_csv_bytes(content)
        dataset_payload, normalized_mapping = build_mapped_dataset(df, mapping_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid mapping JSON: {exc.msg}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to prepare mapped dataset: {exc}")

    invalidate_cache()

    result = await run_audit(
        input_text=json.dumps(dataset_payload),
        num_clusters=num_clusters,
        depth=depth or "standard",
    )
    result["column_mapping"] = normalized_mapping

    await db.insert_audit(
        audit_id=result["audit_id"],
        input_text=result["input_text"],
        bias_score=result["bias"]["bias_score"],
        truth_score=result["truth"]["truth_score"],
        trust_score=result["trust_score"],
        corrected=result.get("corrections", ""),
        audit_type="dataset",
        report_json=result,
        column_mapping=json.dumps(normalized_mapping),
    )

    if result.get("requires_human_review"):
        await db.insert_review(
            audit_id=result["audit_id"],
            trust_score=result["trust_score"],
            input_preview=result["input_text"][:200],
        )
    return result
