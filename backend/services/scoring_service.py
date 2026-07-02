"""Trust-score calculation.

Core formula:
    Trust = alpha*truth + beta*(1-bias) + gamma*confidence

Cluster and distribution checks remain part of the audit pipeline as
diagnostics, but they do not change the trust-score formula.
"""
from typing import Dict
from ..config import get_active_weights


def weighted_score(features: list, weights: list) -> float:
    """Implementation of ML Addon: y = sum(alpha_i * x_i)"""
    return sum(w * x for w, x in zip(weights, features))

def compute_trust_score(
    truth: float,
    bias: float,
    confidence: float,
    cluster: float,
    distribution: float,
) -> Dict[str, float]:
    """Calculate the weighted trust score using the fixed 3-signal formula."""
    active_weights = get_active_weights()
    # Defensive: a partial CUSTOM_WEIGHTS must not KeyError inside every audit.
    w_truth = float(active_weights.get("truth", 0.40))
    w_bias = float(active_weights.get("bias", 0.40))
    w_confidence = float(active_weights.get("confidence", 0.20))
    bias_contrib = (1 - bias)

    # Order must match between features and weights arrays
    features = [truth, bias_contrib, confidence]
    weights_array = [w_truth, w_bias, w_confidence]

    trust_score = weighted_score(features, weights_array)

    components = {
        "truth": truth * w_truth,
        "bias": bias_contrib * w_bias,
        "confidence": confidence * w_confidence,
        "cluster_diagnostic": cluster,
        "distribution_diagnostic": distribution,
    }
    
    trust_score = max(0.0, min(1.0, trust_score))
    result = {"trust_score": trust_score, **components}
    return result
