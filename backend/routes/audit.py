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

    depth = request.depth or (request.audit_options or {}).get("depth") or "standard"
    input_text = request.input_text

    if not input_text and request.dataset_id in {"demo_hiring", "hiring_bias_demo"}:
        from .demo import run_demo_audit
        return await run_demo_audit("hiring_bias_demo")

    if not input_text and request.features is not None and request.labels is not None:
        if not isinstance(request.features, list) or not request.features:
            raise HTTPException(status_code=400, detail="Structured audit requires a non-empty feature matrix.")
        feature_names = request.feature_names
        if not feature_names and request.features and isinstance(request.features[0], list):
            feature_names = [f"f{i}" for i in range(len(request.features[0]))]
        input_text = json.dumps(
            {
                "features": request.features,
                "labels": request.labels,
                "feature_names": feature_names,
                "protected_index": request.protected_index or 0,
            }
        )

    if not input_text:
        raise HTTPException(
            status_code=400,
            detail="Provide input_text, a structured dataset with features+labels, or dataset_id='demo_hiring'.",
        )

    try:
        result = await run_audit(
            input_text=input_text,
            num_clusters=request.num_clusters,
            depth=depth,
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
