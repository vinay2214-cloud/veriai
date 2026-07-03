"""Distribution analysis utilities.
Computes mean, std, skewness, kurtosis and a stability metric that
captures how well the data distribution conforms to expectations.
"""
import numpy as np
from typing import Dict, Tuple

# scipy.stats is imported lazily inside the functions that use it (Phase 2
# startup optimization). scipy alone costs ~0.5 s and pulls in extra RSS at
# import time, none of which is needed until an audit actually runs.


def compute_distribution_stats(data: np.ndarray) -> Dict[str, float]:
    """Return descriptive statistics for a 1‑D array."""
    from scipy import stats as sp_stats
    return {
        "mean": float(np.mean(data)),
        "std": float(np.std(data, ddof=1)) if len(data) > 1 else 0.0,
        "skewness": float(sp_stats.skew(data, bias=False)) if len(data) > 2 else 0.0,
        "kurtosis": float(sp_stats.kurtosis(data, bias=False)) if len(data) > 3 else 0.0,
    }


def distribution_stability(data: np.ndarray) -> float:
    """Compute a stability score in [0, 1].
    Stability penalises high skewness and excess kurtosis.
    A perfectly normal distribution scores 1.0.
    """
    if len(data) < 4:
        return 0.5  # not enough data
    from scipy import stats as sp_stats
    skew = abs(sp_stats.skew(data, bias=False))
    kurt = abs(sp_stats.kurtosis(data, bias=False))
    # Map skew and kurtosis into a penalty — clamp at 1
    penalty = min((skew + kurt / 3.0) / 4.0, 1.0)
    return round(1.0 - penalty, 4)


def compute_distribution_report(data: np.ndarray) -> Tuple[float, Dict[str, float]]:
    """High‑level helper returning (stability_score, stats_dict)."""
    dist_stats = compute_distribution_stats(data)
    stability = distribution_stability(data)
    return stability, dist_stats
