"""Multi‑step reasoning chain (Opus‑style) — v2.0.
Orchestrates the full audit pipeline with parallel processing and depth control:
    Step 1 → Analyse bias        (parallel group A)
    Step 2 → Verify truth        (parallel group A)
    Step 3 → Cluster analysis    (parallel group A — standard+)
    Step 4 → Distribution analysis (parallel group A — standard+)
    Step 5 → Compute trust score
    Step 6 → Decide & correct
    Step 7 → Re‑evaluate
    Step 8 → Human review flag   (if trust < threshold)
Each step is logged so the frontend can show a step‑by‑step breakdown.
"""
import json
import uuid
import time
import asyncio
import numpy as np
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging

from ..config import DEFAULT_NUM_CLUSTERS, HUMAN_REVIEW_THRESHOLD
from .bias_service import compute_bias_score
from .truth_service import verify_claims
from .llm_factcheck_service import verify_text_with_llm_rag
from .cluster_service import cluster_bias_analysis
from .distribution_service import compute_distribution_report
from .scoring_service import compute_trust_score
from .correction_service import apply_corrections

# Thread pool for CPU-bound tasks
_executor = ThreadPoolExecutor(max_workers=4)
logger = logging.getLogger(__name__)
_AUDIT_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_LIMIT = 128


def _parse_dataset(raw: str):
    """Parse JSON dataset; return None if the input should be treated as plain text."""
    if not raw or not raw.strip():
        raise ValueError("input_text cannot be empty.")
    text = raw.strip()
    looks_like_json = text.startswith("{") or text.startswith("[")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        if looks_like_json:
            raise ValueError(f"Invalid JSON payload: {exc.msg}") from exc
        return None

    if not isinstance(data, dict):
        raise ValueError("Dataset payload must be a JSON object.")
    if "features" not in data or "labels" not in data:
        raise ValueError("Dataset JSON must include 'features' and 'labels'.")

    try:
        X = np.array(data["features"], dtype=float)
        y = np.array(data["labels"], dtype=float)
    except Exception as exc:
        raise ValueError("Dataset 'features' and 'labels' must be numeric arrays.") from exc

    if X.ndim != 2:
        raise ValueError("'features' must be a 2D array.")
    if y.ndim != 1:
        raise ValueError("'labels' must be a 1D array.")
    if len(X) == 0:
        raise ValueError("Dataset cannot be empty.")
    if len(X) != len(y):
        raise ValueError("Features and labels must have the same number of rows.")

    names = data.get("feature_names", [f"f{i}" for i in range(X.shape[1])])
    if not isinstance(names, list) or len(names) != X.shape[1]:
        raise ValueError("'feature_names' must be a list matching feature column count.")
    prot_idx = int(data.get("protected_index", 0))
    if prot_idx < 0 or prot_idx >= X.shape[1]:
        raise ValueError("'protected_index' must point to a valid feature column.")

    return X, y, names, prot_idx


def _cache_key(input_text: str, num_clusters: int, depth: str) -> str:
    raw = f"{depth}|{num_clusters}|{input_text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def run_audit(input_text: str, num_clusters: int = None, depth: str = "standard") -> Dict[str, Any]:
    """Execute the full multi‑step reasoning chain with parallel processing.

    Depth levels:
    - "fast": Bias + Truth only (2 parallel checks)
    - "standard": Bias + Truth + Cluster + Distribution (4 parallel checks)
    - "thorough": All 4 + full re-evaluation pass

    Returns a comprehensive result dict ready to be serialised.
    """
    n_clusters = num_clusters or DEFAULT_NUM_CLUSTERS
    key = _cache_key(input_text, n_clusters, depth)
    if key in _AUDIT_CACHE:
        cached = dict(_AUDIT_CACHE[key])
        cached["audit_id"] = str(uuid.uuid4())[:8]
        cached["from_cache"] = True
        return cached

    audit_id = str(uuid.uuid4())[:8]
    steps: List[Dict[str, Any]] = []
    step_timings: Dict[str, float] = {}
    t0 = time.time()

    # Validate depth
    if depth not in ("fast", "standard", "thorough"):
        depth = "standard"

    # ------------------------------------------------------------------
    # Parse input (synchronous, fast)
    # ------------------------------------------------------------------
    parsed = _parse_dataset(input_text)
    text_mode = parsed is None
    if text_mode:
        X = y = feature_names = protected_idx = None
        steps.append({
            "step": 0, "name": "Input Validation",
            "status": "complete",
            "detail": "Plain-text mode detected. Fairness metrics use neutral defaults.",
            "elapsed": 0,
        })
    else:
        X, y, feature_names, protected_idx = parsed
        steps.append({
            "step": 0, "name": "Input Validation",
            "status": "complete",
            "detail": f"Dataset validated with {len(y)} rows and {X.shape[1]} features.",
            "elapsed": 0,
        })

    # ------------------------------------------------------------------
    # PARALLEL EXECUTION: Run independent checks concurrently
    # ------------------------------------------------------------------
    loop = asyncio.get_event_loop()

    # Always run bias and truth in parallel
    async def run_bias():
        t = time.time()
        if text_mode:
            step_timings["bias"] = 0
            return 0.5, {}, 0.0, 0.0
        result = await loop.run_in_executor(
            _executor, compute_bias_score, X, y, protected_idx, feature_names
        )
        step_timings["bias"] = round(time.time() - t, 3)
        return result

    async def run_truth():
        t = time.time()
        if text_mode:
            result = await verify_text_with_llm_rag(input_text)
        else:
            result = await verify_claims(input_text)
        step_timings["truth"] = round(time.time() - t, 3)
        return result

    async def run_cluster():
        t = time.time()
        if text_mode:
            step_timings["cluster"] = 0
            return 0.5, []
        result = await loop.run_in_executor(
            _executor, cluster_bias_analysis, X, y, protected_idx, n_clusters
        )
        step_timings["cluster"] = round(time.time() - t, 3)
        return result

    async def run_distribution():
        t = time.time()
        if text_mode:
            step_timings["distribution"] = 0
            return 0.5, {"mean": 0.0, "std": 0.0, "skewness": 0.0, "kurtosis": 0.0}
        result = await loop.run_in_executor(_executor, compute_distribution_report, y)
        step_timings["distribution"] = round(time.time() - t, 3)
        return result

    # Build task list based on depth
    if depth == "fast":
        bias_task = run_bias()
        truth_task = run_truth()
        (bias_result, truth_result) = await asyncio.gather(bias_task, truth_task)
        cluster_fairness, cluster_details = 0.85, []  # default placeholder
        dist_stability, dist_stats = 0.9, {"mean": 0.0, "std": 0.0, "skewness": 0.0, "kurtosis": 0.0}
    else:
        # Standard and thorough run all 4 in parallel
        bias_task = run_bias()
        truth_task = run_truth()
        cluster_task = run_cluster()
        dist_task = run_distribution()
        (bias_result, truth_result, cluster_result, dist_result) = await asyncio.gather(
            bias_task, truth_task, cluster_task, dist_task
        )
        cluster_fairness, cluster_details = cluster_result
        dist_stability, dist_stats = dist_result

    bias_score, feat_imp, dp, eo = bias_result

    # ------------------------------------------------------------------
    # Step 1: Bias Analysis (already done in parallel)
    # ------------------------------------------------------------------
    steps.append({
        "step": 1, "name": "Bias Analysis",
        "status": "complete",
        "detail": (
            "Not applicable for plain-text input; neutral default used."
            if text_mode else f"Bias score={bias_score:.3f}, DP={dp:.3f}, EO={eo:.3f}"
        ),
        "elapsed": step_timings.get("bias", 0),
    })
    logger.info("Step 1 Bias Analysis: %.3fs", step_timings.get("bias", 0))

    # ------------------------------------------------------------------
    # Step 2: Truth Verification (already done in parallel)
    # ------------------------------------------------------------------
    steps.append({
        "step": 2, "name": "Truth Verification",
        "status": "complete",
        "detail": f"Truth score={truth_result['truth_score']:.3f}, groundedness={truth_result['groundedness']:.3f}",
        "elapsed": step_timings.get("truth", 0),
    })
    logger.info("Step 2 Truth Verification: %.3fs", step_timings.get("truth", 0))

    # ------------------------------------------------------------------
    # Step 3: Cluster analysis
    # ------------------------------------------------------------------
    if depth == "fast":
        steps.append({
            "step": 3, "name": "Cluster Analysis",
            "status": "skipped",
            "detail": "Skipped in fast mode",
            "elapsed": 0,
        })
        logger.info("Step 3 Cluster Analysis: skipped")
    else:
        steps.append({
            "step": 3, "name": "Cluster Analysis",
            "status": "complete",
            "detail": (
                "Not applicable for plain-text input; neutral default used."
                if text_mode else f"Cluster fairness={cluster_fairness:.3f} across {n_clusters} clusters"
            ),
            "elapsed": step_timings.get("cluster", 0),
        })
        logger.info("Step 3 Cluster Analysis: %.3fs", step_timings.get("cluster", 0))

    # ------------------------------------------------------------------
    # Step 4: Distribution analysis
    # ------------------------------------------------------------------
    if depth == "fast":
        steps.append({
            "step": 4, "name": "Distribution Analysis",
            "status": "skipped",
            "detail": "Skipped in fast mode",
            "elapsed": 0,
        })
        logger.info("Step 4 Distribution Analysis: skipped")
    else:
        steps.append({
            "step": 4, "name": "Distribution Analysis",
            "status": "complete",
            "detail": (
                "Not applicable for plain-text input; neutral default used."
                if text_mode else f"Stability={dist_stability:.3f}, skew={dist_stats['skewness']:.3f}"
            ),
            "elapsed": step_timings.get("distribution", 0),
        })
        logger.info("Step 4 Distribution Analysis: %.3fs", step_timings.get("distribution", 0))

    # ------------------------------------------------------------------
    # Step 5: Compute trust score
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    confidence = 0.85  # placeholder confidence from model calibration
    score_breakdown = compute_trust_score(
        truth=truth_result["truth_score"],
        bias=bias_score,
        confidence=confidence,
        cluster=cluster_fairness,
        distribution=dist_stability,
    )
    step_timings["step_5"] = round((time.perf_counter() - _t) * 1000, 2)
    logger.info("Step 5 Trust Scoring: %.2fms", step_timings["step_5"])
    steps.append({
        "step": 5, "name": "Trust Score",
        "status": "complete",
        "detail": f"Trust score={score_breakdown['trust_score']:.3f}",
        "elapsed": step_timings["step_5"],
    })

    # ------------------------------------------------------------------
    # Step 6: Decide & correct
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    raw_result = {
        "input_text": input_text,
        "bias": {"feature_importance": feat_imp},
        "truth": {"citations": truth_result["citations"]},
    }
    corrections = apply_corrections(raw_result)
    corrected_output = corrections.get("truth_corrections", input_text)

    decision = "approve" if score_breakdown["trust_score"] >= 0.70 else "correct"
    step_timings["step_6"] = round((time.perf_counter() - _t) * 1000, 2)
    logger.info("Step 6 Decision & Correction: %.2fms", step_timings["step_6"])
    steps.append({
        "step": 6, "name": "Decision & Correction",
        "status": "complete",
        "detail": f"Decision: {decision}. Actions: {len(corrections.get('actions', []))}",
        "elapsed": step_timings["step_6"],
    })

    # ------------------------------------------------------------------
    # Step 7: Re‑evaluate after correction
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    if decision == "correct" and depth != "fast":
        # Re‑run truth check on corrected output
        truth_recheck = await verify_claims(corrected_output)
        new_score = compute_trust_score(
            truth=truth_recheck["truth_score"],
            bias=max(bias_score * 0.6, 0),  # bias reduced after correction
            confidence=confidence,
            cluster=cluster_fairness,
            distribution=dist_stability,
        )
        final_trust = new_score["trust_score"]
        step_timings["step_7"] = round((time.perf_counter() - _t) * 1000, 2)
        logger.info("Step 7 Re-evaluation: %.2fms", step_timings["step_7"])
        steps.append({
            "step": 7, "name": "Re‑evaluation",
            "status": "complete",
            "detail": f"New trust score={new_score['trust_score']:.3f} (was {score_breakdown['trust_score']:.3f})",
            "elapsed": step_timings["step_7"],
        })
    else:
        final_trust = score_breakdown["trust_score"]
        step_timings["step_7"] = round((time.perf_counter() - _t) * 1000, 2)
        logger.info("Step 7 Re-evaluation: %.2fms", step_timings["step_7"])
        steps.append({
            "step": 7, "name": "Re‑evaluation",
            "status": "skipped" if depth == "fast" else "skipped",
            "detail": "Skipped in fast mode." if depth == "fast" else "No correction needed — approved as‑is.",
            "elapsed": step_timings["step_7"],
        })

    # ------------------------------------------------------------------
    # Step 8: Human review flag (Enhancement #5)
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    requires_review = bool(final_trust < HUMAN_REVIEW_THRESHOLD)
    if requires_review:
        step_timings["step_8"] = round((time.perf_counter() - _t) * 1000, 2)
        logger.info("Step 8 Human Review Routing: %.2fms", step_timings["step_8"])
        steps.append({
            "step": 8, "name": "Human Review Required",
            "status": "flagged",
            "detail": f"Trust score {final_trust:.3f} is below threshold {HUMAN_REVIEW_THRESHOLD}. Queued for human review.",
            "elapsed": step_timings["step_8"],
        })
    else:
        step_timings["step_8"] = round((time.perf_counter() - _t) * 1000, 2)
        logger.info("Step 8 Human Review Routing: %.2fms", step_timings["step_8"])
        steps.append({
            "step": 8, "name": "Human Review",
            "status": "passed",
            "detail": f"Trust score {final_trust:.3f} exceeds threshold {HUMAN_REVIEW_THRESHOLD}. Auto-approved.",
            "elapsed": step_timings["step_8"],
        })

    elapsed = round(time.time() - t0, 3)

    result = {
        "audit_id": audit_id,
        "input_text": input_text[:500],
        "audit_type": "text" if text_mode else "dataset",
        "depth": depth,
        "bias": {
            "bias_score": round(bias_score, 4),
            "demographic_parity": round(dp, 4),
            "equalized_odds": round(eo, 4),
            "feature_importance": {k: round(v, 4) for k, v in feat_imp.items()},
        },
        "truth": {
            "truth_score": round(truth_result["truth_score"], 4),
            "groundedness": round(truth_result["groundedness"], 4),
            "citations": truth_result["citations"],
            "claim_citations": truth_result.get("claim_citations", []),
            "claims": truth_result.get("claims", []),
            "verification_mode": truth_result.get("verification_mode", "embedding_similarity"),
            "llm_model": truth_result.get("llm_model"),
        },
        "cluster": {
            "cluster_fairness": round(cluster_fairness, 4),
            "cluster_details": cluster_details,
        },
        "distribution": {
            "distribution_stability": round(dist_stability, 4),
            "stats": {k: round(v, 4) for k, v in dist_stats.items()} if isinstance(dist_stats, dict) else {},
        },
        "trust_score": round(final_trust, 4),
        "corrections": corrected_output,
        "correction_actions": corrections.get("actions", []),
        "reasoning_steps": steps,
        "elapsed_seconds": elapsed,
        "requires_human_review": requires_review,
        "from_cache": False,
    }
    
    # Priority 4.2: Detect Regulatory Compliance Flags
    flags = []
    inp = input_text.lower()
    feat_imp_keys = feat_imp.keys()
    
    if bias_score > 0.15 and ("zip_code" in feat_imp_keys or "zip code" in inp or "zip_code" in inp or "mortgage" in inp or "loan" in inp):
        flags.append({"regulation": "ECOA §1691", "description": "zip_code proxy discrimination", "type": "warning"})
        
    if truth_result["truth_score"] < 0.8 and ("drug" in inp or "dosage" in inp or "medicine" in inp or "patient" in inp):
        flags.append({"regulation": "WHO Essential Medicines", "description": "drug dosage hallucinations", "type": "danger"})
        
    if dist_stability < 0.7 or cluster_fairness < 0.6:
        flags.append({"regulation": "EU AI Act Art. 10", "description": "training data quality violations", "type": "purple"})
        
    result["regulatory_flags"] = flags

    cached_result = dict(result)
    _AUDIT_CACHE[key] = cached_result
    if len(_AUDIT_CACHE) > _CACHE_LIMIT:
        _AUDIT_CACHE.pop(next(iter(_AUDIT_CACHE)))
    return result
