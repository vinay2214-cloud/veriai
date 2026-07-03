'''backend/services/cluster_service.py'''
"""Cluster analysis utilities.
Provides KMeans clustering on feature vectors and per‑cluster bias metrics.
"""
import numpy as np
from typing import List, Dict, Tuple

# KMeans is imported lazily inside cluster_features (Phase 2 startup optimization).

def cluster_features(X: np.ndarray, n_clusters: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    """Run KMeans on the feature matrix X.
    Returns a tuple (labels, centroids).
    """
    from sklearn.cluster import KMeans

    numeric_df = np.asarray(X, dtype=float)
    numeric_df = np.nan_to_num(numeric_df, nan=0.0, posinf=0.0, neginf=0.0)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    kmeans.fit(numeric_df)
    return kmeans.labels_, kmeans.cluster_centers_

def cluster_bias_analysis(
    X: np.ndarray,
    y: np.ndarray,
    protected_idx: int,
    n_clusters: int = 4,
) -> Tuple[float, List[Dict[str, float]]]:
    """Compute bias per cluster and return an overall cluster fairness score.
    The fairness score is the average of (1 - bias) across clusters.
    Returns (overall_score, per_cluster_details).
    """
    # Cap clusters to number of samples
    actual_clusters = min(n_clusters, len(X))
    if actual_clusters < 2:
        return 0.5, [{"cluster_id": 0, "bias": 0.5, "size": len(X)}]
    labels, _ = cluster_features(X, actual_clusters)
    per_cluster = []
    scores = []
    for cluster_id in range(actual_clusters):
        mask = labels == cluster_id
        if mask.sum() < 2:
            continue
        protected = X[mask, protected_idx]
        try:
            from sklearn.linear_model import LogisticRegression
            clf = LogisticRegression(max_iter=200, solver='liblinear')
            y_cluster = y[mask]
            # Check if labels are homogeneous (only one class) — LR can't fit
            if len(np.unique(y_cluster)) < 2:
                dp = 0.0
            else:
                clf.fit(X[mask], y_cluster)
                preds = clf.predict(X[mask])
                g0 = preds[protected == 0]
                g1 = preds[protected == 1]
                dp = abs((g0.mean() if len(g0) > 0 else 0) - (g1.mean() if len(g1) > 0 else 0))
        except Exception:
            dp = 0.0
        scores.append(1 - dp)
        per_cluster.append({"cluster_id": int(cluster_id), "bias": dp, "size": int(mask.sum())})
    overall = float(np.mean(scores)) if scores else 0.5
    return overall, per_cluster
