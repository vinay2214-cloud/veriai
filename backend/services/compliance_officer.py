"""AI Compliance Officer (Phase 3, Tasks 2 & 8).

Turns a completed audit's raw metrics into the output a senior compliance
consultant would hand a business owner:

    Executive Summary → Business Risk Summary → Compliance Mapping
    → Recommendations → Next Actions → per-audit Customer Value

Everything is deterministic and derived from the real audit numbers (trust / bias /
truth scores and the audit's own ``regulatory_flags``). It runs with no API key and
never fabricates figures. When an LLM key *is* configured, ``summarize(..., llm_polish=
True)`` will best-effort rewrite the prose for extra fluency — but any failure silently
falls back to the deterministic text, so the demo never breaks.

This module does NOT change the trust-score formula or the audit pipeline. It only
reads an existing result dict (live from ``run_audit`` or reconstructed from storage).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..config import TRUST_BANDS, COMPLIANCE_FRAMEWORKS

# NOTE: litellm is imported lazily inside _maybe_llm_polish (not at module top),
# so importing this module — which the audit router pulls in at startup — never
# loads litellm. This preserves the Phase 2 lightweight-startup guarantee.


# ---------------------------------------------------------------------------
# Robust score extraction — works on both the live run_audit result and the
# reconstructed DB record (where scores can live at the top level and/or nested
# under "report").
# ---------------------------------------------------------------------------
def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract(audit: Dict[str, Any]) -> Dict[str, Any]:
    audit = audit or {}
    report = audit.get("report") if isinstance(audit.get("report"), dict) else {}

    def pick(*paths, default=None):
        for container in (audit, report):
            cur = container
            ok = True
            for key in paths:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    ok = False
                    break
            if ok and cur is not None:
                return cur
        return default

    trust = _num(pick("trust_score", default=pick("trust", "trust_score", default=0.0)))
    bias = _num(pick("bias", "bias_score", default=pick("bias_score", default=0.0)))
    truth = _num(pick("truth", "truth_score", default=pick("truth_score", default=0.0)))
    cluster = _num(pick("cluster", "cluster_fairness", default=0.0))
    distribution = _num(pick("distribution", "distribution_stability", default=0.0))
    flags = pick("regulatory_flags", default=[]) or []
    audit_type = pick("audit_type", default="dataset")
    requires_review = bool(pick("requires_human_review", default=trust < TRUST_BANDS["elevated"]))

    return {
        "trust": trust,
        "bias": bias,
        "truth": truth,
        "cluster": cluster,
        "distribution": distribution,
        "flags": flags if isinstance(flags, list) else [],
        "audit_type": audit_type,
        "requires_review": requires_review,
        "audit_id": pick("audit_id", default=audit.get("audit_id")),
    }


def _risk_level(trust: float) -> str:
    if trust < TRUST_BANDS["critical"]:
        return "critical"
    if trust < TRUST_BANDS["elevated"]:
        return "elevated"
    if trust < TRUST_BANDS["moderate"]:
        return "moderate"
    return "low"


_RISK_LABEL = {
    "critical": "Critical",
    "elevated": "Elevated",
    "moderate": "Moderate",
    "low": "Low",
}

# Percent helpers keep the prose in business language (trust as a 0-100 score,
# bias as a disparity percentage).
def _pct(value: float) -> int:
    return int(round(value * 100))


# ---------------------------------------------------------------------------
# Compliance mapping — align real findings to named frameworks.
# ---------------------------------------------------------------------------
def _compliance_mapping(scores: Dict[str, Any]) -> List[Dict[str, str]]:
    bias = scores["bias"]
    truth = scores["truth"]
    flags = scores["flags"]
    mapping: List[Dict[str, str]] = []

    # Start from the audit's own regulatory_flags (already domain-aware).
    flag_texts = []
    for f in flags:
        if isinstance(f, dict):
            flag_texts.append(f"{f.get('regulation', '')}: {f.get('description', '')}".strip(": "))

    def add(fw_key: str, status: str, finding: str):
        fw = COMPLIANCE_FRAMEWORKS.get(fw_key, {})
        mapping.append({
            "framework": fw.get("name", fw_key),
            "reference": fw.get("reference", ""),
            "status": status,          # "pass" | "attention" | "violation"
            "finding": finding,
        })

    # Fairness → EEOC four-fifths / ECOA.
    if bias >= 0.20:
        add("eeoc", "violation",
            f"Measured group disparity of {_pct(bias)}% breaches the EEOC four-fifths "
            "(80%) rule — disparate impact is likely and must be remediated before use.")
        add("ecoa", "attention",
            "If used for credit/lending decisions, this disparity would constitute a fair-"
            "lending risk under ECOA/Regulation B.")
    elif bias >= 0.10:
        add("eeoc", "attention",
            f"Group disparity of {_pct(bias)}% is approaching the EEOC adverse-impact "
            "threshold; document justification and monitor.")
    else:
        add("eeoc", "pass",
            f"Group disparity of {_pct(bias)}% is within the EEOC four-fifths guideline.")

    # Factual grounding → WHO / clinical & general truthfulness.
    if truth < 0.70:
        add("who", "violation" if truth < 0.5 else "attention",
            f"Factual groundedness of {_pct(truth)}% is below the safe-use threshold; "
            "outputs may include unsupported or hallucinated claims.")
    else:
        add("who", "pass",
            f"Factual groundedness of {_pct(truth)}% meets the reliability threshold.")

    # Governance → EU AI Act data governance + NIST AI RMF.
    gov_status = "attention" if (bias >= 0.10 or truth < 0.75) else "pass"
    add("eu_ai_act", gov_status,
        "Data-governance and quality evidence "
        + ("shows gaps that a high-risk AI system must close (Art. 10)."
           if gov_status == "attention" else
           "is consistent with high-risk AI system expectations (Art. 10)."))
    add("nist_ai_rmf", gov_status,
        "Maps to the NIST AI RMF Measure/Manage functions — "
        + ("findings require documented mitigation."
           if gov_status == "attention" else
           "metrics are measured and within tolerance."))

    # GDPR automated decision-making note when protected exposure is implied.
    if flag_texts:
        add("gdpr", "attention",
            "Automated decisions affecting individuals must offer meaningful information "
            "and a route to human review (Art. 22).")

    return mapping


# ---------------------------------------------------------------------------
# Narrative builders (deterministic templates).
# ---------------------------------------------------------------------------
def _executive_summary(scores: Dict[str, Any], risk: str) -> str:
    trust = _pct(scores["trust"])
    bias = _pct(scores["bias"])
    truth = _pct(scores["truth"])
    label = _RISK_LABEL[risk]
    if risk in ("critical", "elevated"):
        stance = (
            f"This AI system carries {label.lower()} trust risk and is not recommended for "
            "production use without remediation."
        )
    elif risk == "moderate":
        stance = (
            f"This AI system is broadly usable but shows {label.lower()} risk that should be "
            "monitored and documented."
        )
    else:
        stance = "This AI system meets VeriAI's trust bar and is suitable for production use."
    return (
        f"VeriAI assessed this {scores['audit_type']} audit at an overall Trust Score of "
        f"{trust}/100 ({label} risk). Fairness disparity measured {bias}% and factual "
        f"groundedness measured {truth}%. {stance}"
    )


def _business_risk_summary(scores: Dict[str, Any], risk: str) -> str:
    bias = _pct(scores["bias"])
    truth = _pct(scores["truth"])
    parts: List[str] = []
    if scores["bias"] >= 0.10:
        parts.append(
            f"a {bias}% demographic disparity that creates legal exposure (discrimination "
            "claims, regulator scrutiny) and reputational risk"
        )
    if scores["truth"] < 0.75:
        parts.append(
            f"factual groundedness of only {truth}%, meaning the system may state unsupported "
            "claims that mislead customers or staff"
        )
    if not parts:
        return (
            "No material business risks were identified. The system's fairness and factual "
            "reliability are within tolerance; residual risk is limited to normal monitoring."
        )
    body = "; and ".join(parts)
    consequence = (
        "Left unaddressed, these issues can translate into regulatory penalties, remediation "
        "cost, and lost customer trust."
    )
    return f"The principal business risks are {body}. {consequence}"


def _recommendations(scores: Dict[str, Any]) -> List[str]:
    recs: List[str] = []
    if scores["bias"] >= 0.20:
        recs.append("Halt production use for affected decisions until bias mitigation is applied and re-verified.")
        recs.append("Apply sample reweighing / threshold adjustment and re-audit to confirm disparity falls below 10%.")
    elif scores["bias"] >= 0.10:
        recs.append("Document business justification for the observed disparity and schedule a mitigation pass.")
    if scores["truth"] < 0.70:
        recs.append("Ground responses in a verified knowledge base and require citations before user-facing display.")
    elif scores["truth"] < 0.85:
        recs.append("Expand the knowledge base coverage to lift factual groundedness above 85%.")
    if scores["distribution"] and scores["distribution"] < 0.7:
        recs.append("Investigate training-data distribution instability (skew/kurtosis) that can degrade fairness over time.")
    if not recs:
        recs.append("Maintain current controls and continue periodic re-auditing to detect drift.")
    recs.append("Retain this report as evidence of AI governance diligence for auditors and regulators.")
    return recs


def _next_actions(scores: Dict[str, Any], risk: str) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    if risk in ("critical", "elevated"):
        actions.append({"action": "Route this audit to human review and hold deployment", "owner": "Compliance Lead", "urgency": "immediate"})
    if scores["bias"] >= 0.10:
        actions.append({"action": "Run bias mitigation and re-audit", "owner": "ML Engineer", "urgency": "high" if scores["bias"] >= 0.2 else "medium"})
    if scores["truth"] < 0.75:
        actions.append({"action": "Improve knowledge-base grounding for factual claims", "owner": "Data/Content Owner", "urgency": "medium"})
    actions.append({"action": "Archive the compliance report for the governance record", "owner": "Compliance Ops", "urgency": "routine"})
    return actions


def _customer_value(scores: Dict[str, Any], risk: str) -> Dict[str, str]:
    """Task 8 — never leave the user wondering what to do next."""
    bias = _pct(scores["bias"])
    truth = _pct(scores["truth"])
    trust = _pct(scores["trust"])
    label = _RISK_LABEL[risk]

    what = f"VeriAI scored this AI system {trust}/100 for trust ({label} risk)."
    why_bits = []
    if scores["bias"] >= 0.10:
        why_bits.append(f"a {bias}% fairness disparity between demographic groups")
    if scores["truth"] < 0.75:
        why_bits.append(f"only {truth}% factual groundedness")
    why = (
        "Driven by " + " and ".join(why_bits) + "."
        if why_bits else
        "The system passed fairness and factual-grounding checks with no material issues."
    )

    if risk in ("critical", "elevated"):
        business_impact = "High — potential legal, regulatory and reputational exposure if deployed as-is."
        compliance_impact = "Likely non-compliant with fairness/AI-governance requirements until remediated."
        recommended_action = "Do not deploy. Remediate the flagged issues and re-audit."
        who = "Compliance Lead + ML Engineer (human review required)."
    elif risk == "moderate":
        business_impact = "Moderate — usable with monitoring; unaddressed issues could grow over time."
        compliance_impact = "Partially compliant; document justification and mitigation plan."
        recommended_action = "Deploy with monitoring and a scheduled mitigation pass."
        who = "Product Owner (with Compliance sign-off)."
    else:
        business_impact = "Low — the system meets the trust bar for production use."
        compliance_impact = "Consistent with fairness and AI-governance expectations."
        recommended_action = "Approve for use; continue periodic re-auditing to catch drift."
        who = "Product Owner (routine sign-off)."

    return {
        "what": what,
        "why": why,
        "business_impact": business_impact,
        "compliance_impact": compliance_impact,
        "recommended_action": recommended_action,
        "who_should_review": who,
    }


# ---------------------------------------------------------------------------
# Optional LLM polish (best-effort; never required).
# ---------------------------------------------------------------------------
def _maybe_llm_polish(result: Dict[str, Any], scores: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return result
    try:
        from litellm import completion  # lazy: only when a key is configured
    except Exception:
        return result
    try:
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        prompt = [
            {"role": "system", "content": (
                "You are a senior AI compliance consultant. Rewrite the given executive summary "
                "and business risk summary to be crisp, professional, and board-ready. Keep every "
                "number exactly as given. Return strict JSON: "
                "{\"executive_summary\": \"...\", \"business_risk_summary\": \"...\"}."
            )},
            {"role": "user", "content": (
                f"executive_summary: {result['executive_summary']}\n"
                f"business_risk_summary: {result['business_risk_summary']}"
            )},
        ]
        response = completion(model=model, api_key=api_key, messages=prompt,
                              temperature=0, response_format={"type": "json_object"}, timeout=20)
        import json
        content = (response.choices[0].message.content or "").strip()
        parsed = json.loads(content) if content else {}
        if parsed.get("executive_summary"):
            result["executive_summary"] = str(parsed["executive_summary"])
        if parsed.get("business_risk_summary"):
            result["business_risk_summary"] = str(parsed["business_risk_summary"])
        result["engine"] = "deterministic+llm"
    except Exception:
        # Any failure → keep the deterministic text. The demo must never break.
        pass
    return result


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------
def summarize(audit: Dict[str, Any], llm_polish: bool = False) -> Dict[str, Any]:
    """Produce a consultant-grade compliance narrative for one audit result.

    ``audit`` may be a live ``run_audit`` result or a reconstructed DB record.
    ``llm_polish`` only takes effect when an LLM key is configured; otherwise the
    deterministic narrative is returned unchanged.
    """
    scores = _extract(audit)
    risk = _risk_level(scores["trust"])

    result: Dict[str, Any] = {
        "risk_level": risk,
        "risk_label": _RISK_LABEL[risk],
        "headline": (
            f"Trust {_pct(scores['trust'])}/100 — {_RISK_LABEL[risk]} risk"
        ),
        "executive_summary": _executive_summary(scores, risk),
        "business_risk_summary": _business_risk_summary(scores, risk),
        "compliance_mapping": _compliance_mapping(scores),
        "recommendations": _recommendations(scores),
        "next_actions": _next_actions(scores, risk),
        "customer_value": _customer_value(scores, risk),
        "scores": {
            "trust": round(scores["trust"], 4),
            "bias": round(scores["bias"], 4),
            "truth": round(scores["truth"], 4),
        },
        "generated_by": "VeriAI AI Compliance Officer",
        "engine": "deterministic",
    }

    if llm_polish:
        result = _maybe_llm_polish(result, scores)
    return result
