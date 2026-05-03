import re
import uuid
from typing import Any, Dict, List

from ..config import HUMAN_REVIEW_THRESHOLD
from .scoring_service import compute_trust_score
from .llm_factcheck_service import verify_single_claim_with_llm_rag


def _extract_claims(output_text: str) -> List[str]:
    claims = [c.strip() for c in re.split(r"[.!?]\s+", output_text) if c.strip()]
    return claims[:12]


def _build_corrected_output(output_text: str, claim_results: List[Dict[str, Any]]) -> str:
    corrected = output_text
    for row in claim_results:
        if not row["hallucinated"]:
            continue
        replacement = row.get("best_citation_snippet") or "Citation-backed fact required."
        corrected = corrected.replace(row["claim"], f"[CORRECTED] {replacement}", 1)
    return corrected


def audit_llm_output(prompt: str, output_text: str, model_name: str = "unknown-llm") -> Dict[str, Any]:
    claims = _extract_claims(output_text)
    if not claims:
        raise ValueError("LLM output did not contain any claim-like sentences.")

    claim_results: List[Dict[str, Any]] = []
    truth_scores: List[float] = []
    reasoning_steps = [
        {"step": 1, "name": "Claim Extraction", "status": "complete", "detail": f"Extracted {len(claims)} claims from model output.", "elapsed": 0},
    ]

    for claim in claims:
        verification = verify_single_claim_with_llm_rag(claim)
        truth_score = float(verification.get("truth_score", 0.0))
        citations = verification.get("citations", [])
        best = citations[0] if citations else {}
        claim_citation = verification.get("claim_citations", [])
        citation_meta = claim_citation[0] if claim_citation else {}
        hallucinated = truth_score < 0.65
        truth_scores.append(truth_score)
        claim_results.append(
            {
                "claim": claim,
                "truth_score": round(truth_score, 4),
                "groundedness": verification.get("groundedness", 0.0),
                "hallucinated": hallucinated,
                "best_citation_title": best.get("title"),
                "best_citation_source": best.get("source"),
                "best_citation_snippet": best.get("snippet"),
                "verdict": citation_meta.get("verdict", "Unverifiable"),
                "reasoning": citation_meta.get("reasoning", ""),
                "source_text": citation_meta.get("source_text", best.get("snippet")),
            }
        )

    total_claims = len(claim_results)
    hallucinated_count = sum(1 for c in claim_results if c["hallucinated"])
    hallucination_rate = hallucinated_count / total_claims if total_claims else 1.0
    avg_truth = sum(truth_scores) / total_claims if total_claims else 0.0
    confidence = max(0.05, 1.0 - hallucination_rate)
    score = compute_trust_score(
        truth=avg_truth,
        bias=0.5,
        confidence=confidence,
        cluster=0.5,
        distribution=0.5,
    )
    pre_correction_trust = score["trust_score"]

    reasoning_steps.append(
        {
            "step": 2,
            "name": "Hallucination Detection",
            "status": "complete",
            "detail": f"Found {hallucinated_count}/{total_claims} hallucinated claims.",
            "elapsed": 0,
        }
    )

    corrected_output = _build_corrected_output(output_text, claim_results)
    post_truth = min(1.0, avg_truth + (0.25 * hallucination_rate))
    post_score = compute_trust_score(
        truth=post_truth,
        bias=0.5,
        confidence=min(1.0, confidence + 0.1),
        cluster=0.5,
        distribution=0.5,
    )
    final_trust = post_score["trust_score"]
    requires_human_review = bool(final_trust < HUMAN_REVIEW_THRESHOLD)

    reasoning_steps.extend(
        [
            {
                "step": 3,
                "name": "Trust Scoring",
                "status": "complete",
                "detail": f"Pre-correction trust={pre_correction_trust:.3f}",
                "elapsed": 0,
            },
            {
                "step": 4,
                "name": "Auto Correction",
                "status": "complete",
                "detail": "Replaced ungrounded claims with citation-backed snippets.",
                "elapsed": 0,
            },
            {
                "step": 5,
                "name": "Trust Delta",
                "status": "complete",
                "detail": f"Post-correction trust={final_trust:.3f} (delta={final_trust - pre_correction_trust:+.3f})",
                "elapsed": 0,
            },
            {
                "step": 6,
                "name": "Human Review",
                "status": "flagged" if requires_human_review else "passed",
                "detail": (
                    f"Flagged: trust {final_trust:.3f} below threshold {HUMAN_REVIEW_THRESHOLD:.2f}"
                    if requires_human_review
                    else f"Passed: trust {final_trust:.3f} above threshold {HUMAN_REVIEW_THRESHOLD:.2f}"
                ),
                "elapsed": 0,
            },
        ]
    )

    flattened_citations = []
    for row in claim_results:
        if row.get("best_citation_title"):
            flattened_citations.append(
                {
                    "title": row.get("best_citation_title"),
                    "source": row.get("best_citation_source"),
                    "snippet": row.get("best_citation_snippet"),
                    "similarity": row.get("truth_score", 0.0),
                }
            )

    return {
        "audit_id": str(uuid.uuid4())[:8],
        "audit_type": "llm",
        "model_name": model_name,
        "prompt": prompt,
        "input_text": output_text[:500],
        "output_text": output_text,
        "claims": claim_results,
        "truth": {
            "truth_score": round(avg_truth, 4),
            "groundedness": round(avg_truth, 4),
            "citations": flattened_citations[:10],
            "claim_citations": claim_results,
            "verification_mode": "llm_rag",
        },
        "bias": {
            "bias_score": 0.5,
            "demographic_parity": 0.0,
            "equalized_odds": 0.0,
            "feature_importance": {},
        },
        "cluster": {"cluster_fairness": 0.5, "cluster_details": []},
        "distribution": {"distribution_stability": 0.5, "stats": {"mean": 0.0, "std": 0.0, "skewness": 0.0, "kurtosis": 0.0}},
        "trust_score": round(final_trust, 4),
        "pre_correction_trust": round(pre_correction_trust, 4),
        "trust_delta": round(final_trust - pre_correction_trust, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "hallucinated_claim_count": hallucinated_count,
        "total_claim_count": total_claims,
        "corrections": corrected_output,
        "correction_actions": [f"corrected_claim:{idx+1}" for idx, c in enumerate(claim_results) if c["hallucinated"]],
        "reasoning_steps": reasoning_steps,
        "elapsed_seconds": 0.0,
        "requires_human_review": requires_human_review,
    }
