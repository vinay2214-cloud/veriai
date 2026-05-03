"""Report retrieval endpoint.
Returns the full audit record from the database.
"""
import io
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from .. import database as db

router = APIRouter()


@router.get("/report/{audit_id}")
async def get_report(audit_id: str):
    """Retrieve a stored audit report by ID."""
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")

    report_json = None
    if len(row) > 9 and row[9]:
        try:
            report_json = json.loads(row[9])
        except Exception:
            report_json = None

    base = {
        "audit_id": row[0],
        "input": row[1],
        "bias_score": row[2],
        "truth_score": row[3],
        "trust_score": row[4],
        "corrected": row[5],
        "audit_type": row[6] if len(row) > 6 else "dataset",
        "model_name": row[7] if len(row) > 7 else None,
        "prompt": row[8] if len(row) > 8 else None,
        "column_mapping": json.loads(row[10]) if len(row) > 10 and row[10] else None,
        "created_at": row[11] if len(row) > 11 else None,
    }
    if report_json:
        base["report"] = report_json
    review = await db.get_review_by_audit(audit_id)
    if review:
        base["review"] = review
    return base


def _pdf_lines(payload: dict):
    lines = [
        f"VeriAI Compliance Report",
        f"Audit ID: {payload.get('audit_id')}",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        f"Trust Score: {payload.get('trust_score')}",
        f"Truth Score: {payload.get('truth_score')}",
        f"Bias Score: {payload.get('bias_score')}",
        "",
        "Input:",
        str(payload.get("input", ""))[:300],
        "",
        "Corrected Output:",
        str(payload.get("corrected", ""))[:300],
    ]
    report = payload.get("report") or {}
    if report.get("reasoning_steps"):
        lines.extend(["", "Reasoning Steps:"])
        for step in report["reasoning_steps"][:10]:
            lines.append(f"- Step {step.get('step')}: {step.get('name')} | {step.get('status')}")
    citations = (report.get("truth") or {}).get("citations", [])
    if citations:
        lines.extend(["", "Citations:"])
        for c in citations[:10]:
            lines.append(f"- {c.get('title')} ({c.get('source')})")
    review = payload.get("review")
    if review:
        lines.extend(["", "Reviewer Trail:"])
        lines.append(f"- Status: {review.get('status')}")
        lines.append(f"- Notes: {review.get('reviewer_notes')}")
        lines.append(f"- Reviewed at: {review.get('reviewed_at')}")
    return lines


@router.get("/reports/{audit_id}/export")
async def export_report(audit_id: str, format: str = Query("json", pattern="^(json|pdf)$")):
    payload = await get_report(audit_id)
    if format == "json":
        return JSONResponse(payload)

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    y = 760
    for line in _pdf_lines(payload):
        pdf.drawString(40, y, str(line)[:110])
        y -= 16
        if y < 40:
            pdf.showPage()
            y = 760
    pdf.save()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=veriai-report-{audit_id}.pdf"},
    )
