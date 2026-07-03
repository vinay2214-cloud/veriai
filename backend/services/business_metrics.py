"""Business analytics & Executive Insights (Phase 3, Tasks 4 & 6).

Aggregates the real SQLite tables into the business KPIs an executive cares about:
today's activity, trust/bias trends, high-risk volume, review load, compliance
health, estimated analyst time saved, and an overall business risk level.

Integrity rule (per the Phase 3 brief): **do not fabricate numbers.** Every figure
here is either counted directly from the database or, in the single case of
"time saved", derived from ONE transparent, configurable constant
(``config.MANUAL_AUDIT_MINUTES``) and always labelled as an estimate with its basis.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .. import database as db
from ..config import MANUAL_AUDIT_MINUTES, TRUST_BANDS


def _round(value, digits=4, default=0.0):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return default


async def _scalar(query: str, params: tuple = ()) -> Any:
    row = await db.fetch_one(query, params)
    return row[0] if row else None


async def _avg_audit_duration_seconds(limit: int = 30) -> float | None:
    """Best-effort average of stored ``elapsed_seconds`` across recent reports.

    Returns None when no report carries a duration (never a fabricated value).
    """
    try:
        rows = await db.fetch_all(
            "SELECT report_json FROM audits WHERE report_json IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    except Exception:
        return None
    durations: List[float] = []
    for (payload,) in rows:
        if not payload:
            continue
        try:
            report = json.loads(payload)
            val = report.get("elapsed_seconds")
            if isinstance(val, (int, float)):
                durations.append(float(val))
        except Exception:
            continue
    if not durations:
        return None
    return round(sum(durations) / len(durations), 3)


def _business_risk_level(avg_trust: float, high_risk_ratio: float) -> Dict[str, str]:
    """Overall portfolio risk from average trust + share of high-risk audits."""
    if avg_trust and avg_trust < TRUST_BANDS["critical"] or high_risk_ratio >= 0.5:
        level, label = "critical", "Critical"
    elif (avg_trust and avg_trust < TRUST_BANDS["elevated"]) or high_risk_ratio >= 0.25:
        level, label = "elevated", "Elevated"
    elif (avg_trust and avg_trust < TRUST_BANDS["moderate"]) or high_risk_ratio > 0:
        level, label = "moderate", "Moderate"
    else:
        level, label = "low", "Low"
    return {"level": level, "label": label}


async def executive_insights() -> Dict[str, Any]:
    """Return the executive-dashboard payload. Fully defensive: any DB hiccup
    yields zeros rather than an error, so the dashboard always renders."""
    try:
        total_audits = int(await _scalar("SELECT COUNT(*) FROM audits") or 0)
        today_audits = int(await _scalar(
            "SELECT COUNT(*) FROM audits WHERE date(created_at) = date('now')"
        ) or 0)
        avg_trust = _round(await _scalar("SELECT AVG(trust_score) FROM audits"), 4)
        avg_bias = _round(await _scalar("SELECT AVG(bias_score) FROM audits"), 4)
        avg_truth = _round(await _scalar("SELECT AVG(truth_score) FROM audits"), 4)

        high_risk_count = int(await _scalar(
            "SELECT COUNT(*) FROM audits WHERE trust_score IS NOT NULL AND trust_score < ?",
            (TRUST_BANDS["elevated"],),
        ) or 0)
        compliant_count = int(await _scalar(
            "SELECT COUNT(*) FROM audits WHERE trust_score IS NOT NULL AND trust_score >= ?",
            (TRUST_BANDS["moderate"],),
        ) or 0)
        scored_count = int(await _scalar(
            "SELECT COUNT(*) FROM audits WHERE trust_score IS NOT NULL"
        ) or 0)
        datasets_processed = int(await _scalar(
            "SELECT COUNT(*) FROM audits WHERE audit_type = 'dataset'"
        ) or 0)

        # Trends (oldest→newest so charts read left-to-right).
        trend_rows = await db.fetch_all(
            "SELECT trust_score, bias_score, created_at FROM audits "
            "ORDER BY created_at DESC LIMIT 20"
        )
        trend_rows = list(reversed(trend_rows or []))
        trust_trend = [_round(r[0], 4) for r in trend_rows if r[0] is not None]
        bias_trend = [_round(r[1], 4) for r in trend_rows if r[1] is not None]

        review_stats = await db.get_review_stats()
        reviews_pending = int(review_stats.get("pending", 0))
        human_reviews = int(
            review_stats.get("approved", 0)
            + review_stats.get("rejected", 0)
            + review_stats.get("escalated", 0)
        )

        avg_duration = await _avg_audit_duration_seconds()

        high_risk_ratio = (high_risk_count / scored_count) if scored_count else 0.0
        compliance_health = round((compliant_count / scored_count) * 100, 1) if scored_count else 0.0
        risk = _business_risk_level(avg_trust, high_risk_ratio)

        minutes_saved = total_audits * MANUAL_AUDIT_MINUTES
        hours_saved = round(minutes_saved / 60, 1)

        return {
            "generated": True,
            "kpis": {
                "today_audits": today_audits,
                "total_audits": total_audits,
                "avg_trust_score": round(avg_trust * 100, 1),   # 0-100 for display
                "avg_bias": avg_bias,
                "avg_truth": avg_truth,
                "high_risk_audits": high_risk_count,
                "reviews_pending": reviews_pending,
                "human_reviews_completed": human_reviews,
                "datasets_processed": datasets_processed,
                "reports_generated": total_audits,
                "compliance_health_pct": compliance_health,
                "avg_audit_duration_seconds": avg_duration,
            },
            "trends": {
                "trust": trust_trend,
                "bias": bias_trend,
            },
            "business_risk_level": risk,
            "time_saved": {
                "hours": hours_saved,
                "minutes": minutes_saved,
                "basis": (
                    f"Estimate: {total_audits} automated audits × "
                    f"{MANUAL_AUDIT_MINUTES} min of manual analyst work each. "
                    "Configurable via VERIAI_MANUAL_AUDIT_MINUTES."
                ),
                "is_estimate": True,
            },
        }
    except Exception:
        return {
            "generated": False,
            "kpis": {
                "today_audits": 0, "total_audits": 0, "avg_trust_score": 0.0,
                "avg_bias": 0.0, "avg_truth": 0.0, "high_risk_audits": 0,
                "reviews_pending": 0, "human_reviews_completed": 0,
                "datasets_processed": 0, "reports_generated": 0,
                "compliance_health_pct": 0.0, "avg_audit_duration_seconds": None,
            },
            "trends": {"trust": [], "bias": []},
            "business_risk_level": {"level": "low", "label": "Low"},
            "time_saved": {"hours": 0.0, "minutes": 0, "basis": "No audits yet.", "is_estimate": True},
        }
