"""AI Review Manager (Phase 3, Task 3).

The human-review queue already exists (``routes/review.py`` + ``database.py``). This
service acts as an AI shift-manager on top of it: for each pending item it estimates
severity and business impact, recommends who should review it, how urgently, and what
action to take — then orders the queue so the most consequential items surface first.

It is advisory only. Humans still approve / reject / escalate through the unchanged
existing endpoints; this just tells them where to look first and why. Deterministic,
no API key required, no fabricated data — every signal is derived from the audit's real
trust / bias / truth scores that the queue already carries.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import TRUST_BANDS


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _severity(trust: float, bias: float, truth: float) -> str:
    """Worst-case of the three signals drives severity."""
    if trust < TRUST_BANDS["critical"] or bias >= 0.25 or truth < 0.50:
        return "critical"
    if trust < TRUST_BANDS["elevated"] or bias >= 0.15 or truth < 0.70:
        return "high"
    if trust < TRUST_BANDS["moderate"] or bias >= 0.10 or truth < 0.80:
        return "medium"
    return "low"


_SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}

_URGENCY = {
    "critical": "immediate (within 4 hours)",
    "high": "same day (within 24 hours)",
    "medium": "this week",
    "low": "routine",
}


def _business_impact(severity: str, bias: float, truth: float) -> str:
    if severity == "critical":
        driver = "discrimination/legal exposure" if bias >= 0.15 else "unsafe or false outputs"
        return f"High — {driver}; a wrong decision here is costly to the business and customers."
    if severity == "high":
        return "Elevated — material fairness or factual risk that could affect real decisions."
    if severity == "medium":
        return "Moderate — worth confirming before this pattern scales."
    return "Low — minor; review for completeness."


def _recommended_reviewer(bias: float, truth: float, severity: str) -> str:
    # Route by the dominant failure mode.
    if bias >= 0.15 and bias >= (1.0 - truth):
        base = "Compliance / Fairness Lead"
    elif truth < 0.70:
        base = "Domain Expert (factual accuracy)"
    else:
        base = "AI Product Owner"
    if severity == "critical":
        return f"{base} + Compliance sign-off"
    return base


def _recommended_action(severity: str, bias: float, truth: float) -> str:
    if severity == "critical":
        return "Reject or escalate — hold deployment until remediated and re-audited."
    if severity == "high":
        if bias >= 0.15:
            return "Escalate for bias mitigation before approval."
        return "Reject pending factual grounding fixes, or approve with documented caveats."
    if severity == "medium":
        return "Approve with monitoring, or request a targeted fix."
    return "Approve — low risk."


def _priority_score(trust: float, bias: float, truth: float, severity: str) -> float:
    """Higher = review sooner. Combines severity rank with metric distance from safe."""
    sev = _SEVERITY_RANK[severity] * 100
    risk_gap = (1.0 - trust) * 40 + bias * 40 + (1.0 - truth) * 20
    return round(sev + risk_gap, 2)


def analyze_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``item`` enriched with AI review guidance (non-destructive copy)."""
    trust = _num(item.get("trust_score"))
    bias = _num(item.get("bias_score"))
    truth = _num(item.get("truth_score"))
    severity = _severity(trust, bias, truth)

    enriched = dict(item)
    enriched["ai_review"] = {
        "severity": severity,
        "urgency": _URGENCY[severity],
        "business_impact": _business_impact(severity, bias, truth),
        "recommended_reviewer": _recommended_reviewer(bias, truth, severity),
        "recommended_action": _recommended_action(severity, bias, truth),
        "priority_score": _priority_score(trust, bias, truth, severity),
        "engine": "deterministic",
    }
    return enriched


def prioritize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich and order a review queue so the highest-priority items come first.

    Only pending items are re-ordered by priority; already-actioned items keep their
    relative position at the end so the queue view stays stable.
    """
    if not items:
        return []
    enriched = [analyze_item(it) for it in items]
    pending = [e for e in enriched if str(e.get("status", "pending")) == "pending"]
    other = [e for e in enriched if str(e.get("status", "pending")) != "pending"]
    pending.sort(key=lambda e: e["ai_review"]["priority_score"], reverse=True)
    return pending + other


def queue_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll-up counts for the review manager header."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for it in items:
        sev = (it.get("ai_review") or {}).get("severity")
        if sev in counts:
            counts[sev] += 1
    top = None
    pending = [it for it in items if str(it.get("status", "pending")) == "pending"]
    if pending:
        top = max(pending, key=lambda e: (e.get("ai_review") or {}).get("priority_score", 0))
    return {
        "severity_counts": counts,
        "pending_total": len(pending),
        "top_priority_audit_id": (top or {}).get("audit_id"),
    }
