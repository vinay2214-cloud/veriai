"""Full audit endpoints, including mapped CSV ingestion."""
import json
import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from ..models import AuditRequest
from ..services.reasoning_chain import run_audit
from ..services.truth_service import invalidate_cache
from ..services.csv_mapping_service import read_csv_bytes, infer_csv_schema, build_mapped_dataset
from ..services import compliance_officer
from .. import database as db

router = APIRouter()
logger = logging.getLogger(__name__)


def _attach_ai_summary(result: dict) -> dict:
    """Phase 3 — attach the deterministic AI business/compliance narrative to an
    audit result (Task 8). Additive: adds one 'ai_summary' key, never mutates
    existing keys. Uses the deterministic core only (no LLM) so audit latency is
    unchanged; the LLM-polished version is available on demand via
    GET /api/ai/compliance-report/{id}. Best-effort: any failure leaves the audit
    result exactly as it was."""
    try:
        result["ai_summary"] = compliance_officer.summarize(result)
    except Exception:
        logger.exception("Failed to attach ai_summary for %s", result.get("audit_id"))
    return result


@router.post("/audit")
async def audit(request: AuditRequest):
    """Run the full multi-step audit pipeline with parallel processing.

    Emits one structured ``audit_timing`` log per request with per-stage latency
    (validation, audit execution, compliance summary, persistence, serialization)
    so production latency is observable without any debug prints.
    """
    t_start = time.perf_counter()
    # Invalidate truth cache to pick up any new KB entries
    invalidate_cache()

    depth = request.depth or (request.audit_options or {}).get("depth") or "fast"
    input_text = request.input_text

    if not input_text and request.dataset_id in {"demo_hiring", "hiring_bias_demo"}:
        from .demo_routes import run_demo_audit
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
    validation_ms = round((time.perf_counter() - t_start) * 1000, 2)

    t_audit = time.perf_counter()
    try:
        result = await run_audit(
            input_text=input_text,
            num_clusters=request.num_clusters,
            depth=depth,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_ms = round((time.perf_counter() - t_audit) * 1000, 2)

    t_comp = time.perf_counter()
    result = _attach_ai_summary(result)
    compliance_ms = round((time.perf_counter() - t_comp) * 1000, 2)

    # Persist to SQLite. A DB hiccup must not discard an already-completed audit.
    t_persist = time.perf_counter()
    try:
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
    except Exception:
        logger.exception("Failed to persist audit %s", result.get("audit_id"))
    persist_ms = round((time.perf_counter() - t_persist) * 1000, 2)

    _log_audit_timing(result, validation_ms, audit_ms, compliance_ms, persist_ms, t_start)
    return result


def _log_audit_timing(result, validation_ms, audit_ms, compliance_ms, persist_ms, t_start):
    """Emit one structured timing line. Serialization is measured here (bounded by
    the persisted-report size cap, so sub-millisecond) to complete the stage picture
    without adding meaningful latency."""
    t_ser = time.perf_counter()
    try:
        response_bytes = len(json.dumps(result, default=str))
    except Exception:
        response_bytes = -1
    serialize_ms = round((time.perf_counter() - t_ser) * 1000, 2)
    total_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(
        "audit_timing",
        extra={
            "event": "audit_timing",
            "audit_id": result.get("audit_id"),
            "depth": result.get("depth"),
            "audit_type": result.get("audit_type"),
            "from_cache": result.get("from_cache", False),
            "trust_score": result.get("trust_score"),
            "stages_ms": {
                "validation": validation_ms,
                "audit_execution": audit_ms,
                "compliance_summary": compliance_ms,
                "persistence": persist_ms,
                "serialization": serialize_ms,
            },
            "total_ms": total_ms,
            "response_bytes": response_bytes,
        },
    )


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
    depth: Optional[str] = Form("fast"),
):
    """Run audit from a raw CSV + user-provided column mapping."""
    t_start = time.perf_counter()
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
    validation_ms = round((time.perf_counter() - t_start) * 1000, 2)

    t_audit = time.perf_counter()
    try:
        result = await run_audit(
            input_text=json.dumps(dataset_payload),
            num_clusters=num_clusters,
            depth=depth or "fast",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_ms = round((time.perf_counter() - t_audit) * 1000, 2)
    result["column_mapping"] = normalized_mapping
    t_comp = time.perf_counter()
    result = _attach_ai_summary(result)
    compliance_ms = round((time.perf_counter() - t_comp) * 1000, 2)

    t_persist = time.perf_counter()
    try:
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
    except Exception:
        logger.exception("Failed to persist mapped audit %s", result.get("audit_id"))
    persist_ms = round((time.perf_counter() - t_persist) * 1000, 2)

    _log_audit_timing(result, validation_ms, audit_ms, compliance_ms, persist_ms, t_start)
    return result
