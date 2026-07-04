"""Report retrieval endpoint.
Returns the full audit record from the database.
"""
import io
import json
from datetime import datetime, UTC
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
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

    column_mapping = None
    if len(row) > 10 and row[10]:
        try:
            column_mapping = json.loads(row[10])
        except Exception:
            column_mapping = None

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
        "column_mapping": column_mapping,
        "created_at": row[11] if len(row) > 11 else None,
    }
    if report_json:
        base["report"] = report_json
    review = await db.get_review_by_audit(audit_id)
    if review:
        base["review"] = review
    return base


@router.get("/reports/{audit_id}/export")
async def export_report(audit_id: str, format: str = Query("json", pattern="^(json|pdf)$")):
    payload = await get_report(audit_id)
    if format == "json":
        return JSONResponse(payload)

    # Import reportlab lazily — it is only needed for PDF export, so this keeps
    # a heavy dependency off the process-startup import path.
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#3b82f6'), spaceAfter=20)
    h2_style = ParagraphStyle(name='H2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1f2937'), spaceAfter=10, spaceBefore=15)
    normal_style = styles['Normal']
    
    story = []
    
    # Title
    story.append(Paragraph(f"VeriAI Trust Audit Report", title_style))
    story.append(Paragraph(f"<b>Audit ID:</b> {payload.get('audit_id')}", normal_style))
    story.append(Paragraph(f"<b>Generated Date:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Scores Table
    trust = (payload.get('trust_score') or 0) * 100
    truth = (payload.get('truth_score') or 0) * 100
    bias = (payload.get('bias_score') or 0) * 100
    
    score_data = [
        ["Trust Score", "Truth Score", "Bias Score"],
        [f"{trust:.1f}%", f"{truth:.1f}%", f"{bias:.1f}%"]
    ]
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#374151')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('TOPPADDING', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,1), 16),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor('#10b981') if trust >= 70 else colors.HexColor('#ef4444')),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
    ])
    score_table = Table(score_data, colWidths=[2*inch, 2*inch, 2*inch])
    score_table.setStyle(t_style)
    story.append(score_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Input/Output
    story.append(Paragraph("Audit Details", h2_style))
    input_text = str(payload.get("input", ""))[:500] + ("..." if len(str(payload.get("input", ""))) > 500 else "")
    story.append(Paragraph(f"<b>Original Input:</b><br/>{input_text}", normal_style))
    story.append(Spacer(1, 0.1*inch))
    
    corrected_text = str(payload.get("corrected", ""))[:500] + ("..." if len(str(payload.get("corrected", ""))) > 500 else "")
    story.append(Paragraph(f"<b>Corrected Output (Auto-Mitigated):</b><br/>{corrected_text}", normal_style))
    
    report = payload.get("report") or {}
    
    # Correction Log
    corrections = report.get("corrections")
    if corrections:
        story.append(Paragraph("Correction Log", h2_style))
        story.append(Paragraph(f"<i>{corrections}</i>", normal_style))
        
    # Citations
    citations = (report.get("truth") or {}).get("citations", [])
    if citations:
        story.append(Paragraph("Truth Citations (RAG)", h2_style))
        for i, c in enumerate(citations[:5]):
            story.append(Paragraph(f"<b>[{i+1}] {c.get('title', 'Unknown Source')}</b>", normal_style))
            story.append(Paragraph(f"Source: <i>{c.get('source', 'N/A')}</i> | Similarity: {c.get('similarity', 0)*100:.1f}%", normal_style))
            snippet = c.get('snippet', '')
            story.append(Paragraph(f"\"{snippet}\"", normal_style))
            story.append(Spacer(1, 0.1*inch))

    # Pipeline Reasoning
    reasoning = report.get("reasoning_steps")
    if reasoning:
        story.append(Paragraph("8-Step Reasoning Pipeline", h2_style))
        for step in reasoning:
            step_status = str(step.get('status') or 'unknown')
            status_color = "#10b981" if step_status == 'complete' else "#ef4444"
            story.append(Paragraph(
                f"<b>Step {step.get('step')}: {step.get('name')}</b> <font color='{status_color}'>[{step_status.upper()}]</font>",
                normal_style
            ))
            story.append(Paragraph(f"Detail: {step.get('detail')}", normal_style))
            story.append(Spacer(1, 0.05*inch))
            
    review = payload.get("review")
    if review:
        story.append(Paragraph("Human Review Trail", h2_style))
        story.append(Paragraph(f"<b>Status:</b> {str(review.get('status') or 'unknown').upper()}", normal_style))
        story.append(Paragraph(f"<b>Notes:</b> {review.get('reviewer_notes')}", normal_style))
        story.append(Paragraph(f"<b>Date:</b> {review.get('reviewed_at')}", normal_style))

    try:
        doc.build(story)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render PDF report: {exc}")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=veriai-report-{audit_id}.pdf"},
    )
