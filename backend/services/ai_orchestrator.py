"""AI Audit Orchestrator (Phase 3, Task 1).

Acts as an intelligent operations manager: instead of asking the user to hand-pick
every audit option, it inspects the *characteristics* of an uploaded dataset (the
schema produced by ``csv_mapping_service.infer_csv_schema``) and recommends a
complete audit configuration — profile, depth, compliance profile, explainability
level, review priority and report detail — with a plain-English rationale.

This is a deterministic expert system: it always runs on the Render free tier with
no API key and never fabricates. It reads only real, inferred dataset facts. The
``compliance_profile`` it returns is one of the existing ``config.INDUSTRY_PRESETS``
keys, so the recommendation plugs straight into the current weighting logic without
changing anything.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Sensitive-domain keyword signals. Matching is done on lower-cased column names.
# Each hit contributes evidence toward a compliance profile + protected attributes.
# VeriAI stays domain-AGNOSTIC: these signals only influence recommendations,
# compliance framework, and report wording — never the audit engine or weighting math.
_DOMAIN_SIGNALS = {
    "hiring": [
        "gender", "sex", "race", "ethnicity", "age", "disability", "veteran",
        "applicant", "candidate", "hire", "hired", "interview", "resume",
        "promotion",
    ],
    "finance": [
        "loan", "credit", "mortgage", "income", "debt", "default", "fico",
        "collateral", "approval", "lending", "transaction",
    ],
    "healthcare": [
        "patient", "diagnosis", "drug", "dose", "dosage", "treatment", "clinical",
        "disease", "symptom", "mortality", "readmission", "icd", "medical",
    ],
    "insurance": [
        "premium", "claim", "policyholder", "underwrit", "actuarial", "coverage",
        "deductible", "insured", "risk_score", "peril",
    ],
    "education": [
        "student", "grade", "gpa", "admission", "enrollment", "scholarship",
        "school", "graduation", "test_score", "tuition",
    ],
    "government": [
        "benefit", "eligibility", "citizen", "welfare", "tax", "permit",
        "applicant_id", "case_id", "public", "constituent",
    ],
}

# Domain → (weighting preset key that already exists in config.INDUSTRY_PRESETS,
# primary compliance framework label). The preset keeps the audit ENGINE untouched
# (new domains reuse an existing, validated weight profile); the framework label is
# used only for recommendation + report wording.
DOMAIN_PROFILES = {
    "hiring":     {"preset": "hiring",     "framework": "EEOC / Title VII (employment fairness)"},
    "finance":    {"preset": "finance",    "framework": "ECOA / Fair Lending (Regulation B)"},
    "healthcare": {"preset": "healthcare", "framework": "HIPAA / clinical safety & FDA SaMD guidance"},
    "insurance":  {"preset": "finance",    "framework": "NAIC model bulletin / fair pricing & underwriting"},
    "education":  {"preset": "general",    "framework": "FERPA / equal educational access"},
    "government": {"preset": "general",    "framework": "OMB M-24-10 / algorithmic accountability"},
    "general":    {"preset": "general",    "framework": "EU AI Act & NIST AI RMF (general governance)"},
}

# Column names that, regardless of domain, denote a legally protected attribute.
_PROTECTED_HINTS = (
    "gender", "sex", "race", "ethnicity", "age", "disability", "religion",
    "nationality", "national_origin", "marital", "pregnan", "veteran", "zip",
    "postal", "orientation",
)


def _detect_protected_attributes(columns: List[Dict[str, Any]]) -> List[str]:
    found: List[str] = []
    for col in columns:
        name = str(col.get("name", "")).lower()
        if any(hint in name for hint in _PROTECTED_HINTS):
            found.append(col.get("name"))
    return found


def _score_domains(columns: List[Dict[str, Any]]) -> Dict[str, int]:
    scores = {domain: 0 for domain in _DOMAIN_SIGNALS}
    names = [str(c.get("name", "")).lower() for c in columns]
    for domain, keywords in _DOMAIN_SIGNALS.items():
        for name in names:
            if any(kw in name for kw in keywords):
                scores[domain] += 1
    return scores


def recommend_audit_profile(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recommend a full audit configuration from an inferred dataset schema.

    ``schema`` is the dict returned by ``infer_csv_schema`` — it must contain
    ``columns`` (list of ``{name, type, suggested_role, ...}``) and ``row_count``.
    Returns a recommendation dict plus a human-readable ``rationale`` list. All
    fields are derived from real dataset facts; nothing is invented.
    """
    columns = schema.get("columns", []) if isinstance(schema, dict) else []
    row_count = int(schema.get("row_count", 0) or 0)
    col_count = len(columns)

    protected = _detect_protected_attributes(columns)
    domain_scores = _score_domains(columns)
    top_domain = max(domain_scores, key=domain_scores.get) if domain_scores else "general"
    has_domain_signal = domain_scores.get(top_domain, 0) > 0

    rationale: List[str] = []

    # --- Depth: scale analysis effort to dataset size/complexity ---------------
    if row_count >= 2000 or col_count >= 15:
        depth = "thorough"
        rationale.append(
            f"Dataset is large ({row_count:,} rows × {col_count} columns) — recommending "
            "a thorough audit (full re-evaluation pass) for statistically robust findings."
        )
    elif row_count <= 200 and col_count <= 6:
        depth = "fast"
        rationale.append(
            f"Small dataset ({row_count:,} rows × {col_count} columns) — a fast audit "
            "(bias + truth) returns results quickly without loss of signal."
        )
    else:
        depth = "standard"
        rationale.append(
            f"Mid-sized dataset ({row_count:,} rows × {col_count} columns) — recommending "
            "a standard audit (bias, truth, cluster and distribution analysis)."
        )

    # --- Compliance profile: map detected domain to an EXISTING weight preset ---
    # The audit engine is untouched — new domains reuse a validated preset; only the
    # framework label + wording are domain-specific.
    effective_domain = top_domain if has_domain_signal else "general"
    domain_profile = DOMAIN_PROFILES.get(effective_domain, DOMAIN_PROFILES["general"])
    compliance_profile = domain_profile["preset"]
    compliance_framework = domain_profile["framework"]
    if has_domain_signal:
        rationale.append(
            f"Column names indicate a {effective_domain} use case "
            f"({domain_scores[top_domain]} domain signal(s)); primary framework: "
            f"{compliance_framework}. Applying the '{compliance_profile}' weighting preset."
        )
    else:
        rationale.append(
            "No strong domain signal detected in the column names; using the general-purpose "
            "compliance preset and governance frameworks (EU AI Act, NIST AI RMF)."
        )

    # --- Explainability level: driven by protected-attribute exposure ----------
    if protected:
        explainability_level = "high"
        rationale.append(
            "Protected attribute(s) present (" + ", ".join(protected[:5]) + ") — enabling "
            "high explainability so any disparate impact is fully traceable per feature."
        )
    else:
        explainability_level = "standard"
        rationale.append(
            "No obvious protected attributes detected — standard explainability is sufficient."
        )

    # --- Review priority: sensitive domain OR protected attrs raise stakes -----
    if protected and has_domain_signal:
        review_priority = "high"
        rationale.append(
            "Regulated domain combined with protected attributes — flagging for high review "
            "priority regardless of trust score."
        )
    elif protected or has_domain_signal:
        review_priority = "medium"
    else:
        review_priority = "standard"

    # --- Report detail: executives need narrative for regulated use cases ------
    report_detail = "executive" if has_domain_signal or protected else "standard"

    # --- Overall audit profile label (human-facing summary) --------------------
    # Label uses the specific detected domain (e.g. Insurance) even though the
    # underlying weight preset may reuse an existing profile.
    if has_domain_signal:
        audit_profile = f"{effective_domain.title()} Compliance Audit"
    elif protected:
        audit_profile = "Fairness-Focused Audit"
    else:
        audit_profile = "General Trust Audit"

    return {
        "audit_profile": audit_profile,
        "depth": depth,
        "compliance_profile": compliance_profile,   # existing preset key (engine-safe)
        "compliance_framework": compliance_framework,
        "explainability_level": explainability_level,
        "review_priority": review_priority,
        "report_detail": report_detail,
        "detected_protected_attributes": protected,
        "detected_domain": effective_domain,
        "supported_domains": list(DOMAIN_PROFILES.keys()),
        "rationale": rationale,
        "engine": "deterministic",
        "summary": (
            f"AI recommends a {audit_profile.lower()} at {depth} depth with "
            f"{explainability_level} explainability and {review_priority} review priority."
        ),
    }
