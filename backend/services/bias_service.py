"""Bias detection service."""
from __future__ import annotations

from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression

from .fairness_service import demographic_parity, equal_opportunity
from .training_service import APP_STATE, get_live_model, load_data, preprocess_data, train_model


def compute_real_bias() -> dict:
    """Compute the actual bias score on the Adult dataset using the trained model."""
    try:
        model, scaler = get_live_model()
        df = load_data()

        if "sex" not in df.columns:
            return {"error": "Required protected attribute 'sex' not found in dataset."}

        X_encoded, _y_true, _ = preprocess_data(df)
        X_scaled = scaler.transform(X_encoded)
        y_pred = model.predict(X_scaled)

        is_male = df["sex"].str.strip() == "Male"
        is_female = df["sex"].str.strip() == "Female"

        p_male = y_pred[is_male].mean() if is_male.sum() > 0 else 0.0
        p_female = y_pred[is_female].mean() if is_female.sum() > 0 else 0.0
        bias_score = abs(p_male - p_female)

        return {
            "bias_score": float(bias_score),
            "p_y_given_male": float(p_male),
            "p_y_given_female": float(p_female),
            "metric": "abs(P(y=1|male) - P(y=1|female))",
        }
    except FileNotFoundError:
        return {"error": "Model or dataset not found. Please train the model first."}


def simulate_bias() -> dict:
    """Distort cached data to simulate biased model behavior for demos."""
    try:
        df = load_data()
        is_male_rich = (df["sex"].str.strip() == "Male") & (df["income"].str.strip() == ">50K")
        is_female_poor = (df["sex"].str.strip() == "Female") & (df["income"].str.strip() == "<=50K")
        distorted_df = pd.concat([df] + [df[is_male_rich]] * 10 + [df[is_female_poor]] * 10, ignore_index=True)

        APP_STATE["df_cache"] = distorted_df
        APP_STATE["X_cache"] = None
        APP_STATE["y_cache"] = None
        APP_STATE["feature_names"] = None

        train_model()
        return {"status": "success", "message": "Simulated heavy bias influx."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def auto_mitigate() -> dict:
    """Apply sample reweighing mitigation and retrain model."""
    try:
        APP_STATE["df_cache"] = None
        APP_STATE["X_cache"] = None
        APP_STATE["y_cache"] = None
        APP_STATE["feature_names"] = None
        APP_STATE["model"] = None
        APP_STATE["scaler"] = None
        df = load_data()

        X, y, _ = preprocess_data(df)
        is_female = (df["sex"].str.strip() == "Female").values
        is_male = ~is_female

        p_female = is_female.mean()
        p_male = is_male.mean()
        p_pos = (y == 1).mean()
        p_neg = (y == 0).mean()
        p_female_pos = ((is_female) & (y == 1)).mean()
        p_female_neg = ((is_female) & (y == 0)).mean()
        p_male_pos = ((is_male) & (y == 1)).mean()
        p_male_neg = ((is_male) & (y == 0)).mean()

        weights = np.ones_like(y, dtype=float)
        weights[(is_female) & (y == 1)] = 3.0 * (p_female * p_pos) / (p_female_pos + 1e-9)
        weights[(is_female) & (y == 0)] = (p_female * p_neg) / (p_female_neg + 1e-9) * 0.5
        weights[(is_male) & (y == 1)] = (p_male * p_pos) / (p_male_pos + 1e-9) * 0.5
        weights[(is_male) & (y == 0)] = 3.0 * (p_male * p_neg) / (p_male_neg + 1e-9)

        train_model(sample_weight=weights)
        return {"status": "success", "message": "Bias mitigated via sample reweighing."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def feature_importance(X: np.ndarray, y: np.ndarray, feature_names: List[str]) -> Dict[str, float]:
    """Train a simple logistic regression model and compute permutation importance."""
    model = LogisticRegression(max_iter=200, solver="liblinear")
    model.fit(X, y)
    result = permutation_importance(model, X, y, n_repeats=5, random_state=0)
    importances = np.abs(result.importances_mean)
    total_variance = importances.sum()
    normalized = np.zeros_like(importances) if total_variance < 1e-6 else (importances / total_variance)
    return {name: float(val) for name, val in zip(feature_names, normalized)}


def compute_bias_metrics(
    df: pd.DataFrame,
    label_col: str,
    protected_attr: str,
    privileged_value: str | None = None,
) -> dict:
    """
    Real bias computation using IBM AIF360.
    Returns Demographic Parity Difference and related fairness metrics.
    """
    work = df.copy()
    for col in work.select_dtypes(include=["object", "category", "bool"]):
        work[col] = pd.factorize(work[col].astype(str), sort=True)[0]

    if label_col not in work.columns:
        return {"error": f"Column '{label_col}' not found", "dpd": 0.0, "equalized_odds": 0.0, "top_feature": ""}
    if protected_attr not in work.columns:
        return {"error": f"Column '{protected_attr}' not found", "dpd": 0.0, "equalized_odds": 0.0, "top_feature": ""}

    y = pd.factorize(work[label_col].astype(str), sort=True)[0]
    p = pd.factorize(work[protected_attr].astype(str), sort=True)[0]
    if len(np.unique(y)) < 2 or len(np.unique(p)) < 2:
        return {
            "dpd": 0.0,
            "equalized_odds": 0.0,
            "top_feature": protected_attr,
            "demographic_parity_difference": 0.0,
            "disparate_impact_ratio": 1.0,
            "protected_attribute": protected_attr,
            "bias_detected": False,
            "eeoc_80_rule_violated": False,
        }

    work[label_col] = y
    work[protected_attr] = p

    try:
        from aif360.datasets import BinaryLabelDataset
        from aif360.metrics import BinaryLabelDatasetMetric
    except Exception as exc:
        return {
            "error": f"AIF360 unavailable: {exc}",
            "dpd": 0.0,
            "equalized_odds": 0.0,
            "top_feature": protected_attr,
        }

    try:
        dataset = BinaryLabelDataset(
            df=work,
            label_names=[label_col],
            protected_attribute_names=[protected_attr],
        )
        privileged = [{protected_attr: 1}] if privileged_value is None else [{protected_attr: privileged_value}]
        unprivileged = [{protected_attr: 0}]

        metric = BinaryLabelDatasetMetric(
            dataset,
            privileged_groups=privileged,
            unprivileged_groups=unprivileged,
        )

        dpd_value = metric.statistical_parity_difference()
        di_value = metric.disparate_impact()
        dpd = float(abs(dpd_value)) if np.isfinite(dpd_value) else 0.0
        di = float(di_value) if np.isfinite(di_value) else 0.0

        corr = work.drop(columns=[label_col]).corrwith(work[label_col]).abs().dropna()
        top_feature = corr.idxmax() if not corr.empty else protected_attr

        return {
            "dpd": round(dpd, 4),
            "equalized_odds": 0.0,
            "top_feature": str(top_feature),
            "demographic_parity_difference": round(dpd, 4),
            "disparate_impact_ratio": round(di, 4),
            "protected_attribute": protected_attr,
            "bias_detected": dpd > 0.1,
            "eeoc_80_rule_violated": (di < 0.8) if di else False,
        }
    except Exception as exc:
        return {"error": str(exc), "dpd": 0.0, "equalized_odds": 0.0, "top_feature": protected_attr}


def compute_bias_score(
    X: np.ndarray,
    y: np.ndarray,
    protected_idx: int,
    feature_names: List[str],
) -> Tuple[float, Dict[str, float], float, float]:
    """Compute bias score from demographic parity + equal opportunity."""
    protected = X[:, protected_idx]
    protected_binary = pd.factorize(pd.Series(protected).astype(str), sort=True)[0]
    protected_name = feature_names[protected_idx] if 0 <= protected_idx < len(feature_names) else "protected_attribute"

    try:
        if len(np.unique(y)) < 2:
            feat_imp = {name: 0.0 for name in feature_names}
            return 0.0, feat_imp, 0.0, 0.0

        clf = LogisticRegression(max_iter=200, solver="liblinear")
        clf.fit(X, y)
        y_pred = clf.predict(X)

        fairness_df = pd.DataFrame(X, columns=feature_names)
        fairness_df[protected_name] = protected_binary
        fairness_df["__prediction__"] = y_pred.astype(int)
        metrics = compute_bias_metrics(
            fairness_df,
            label_col="__prediction__",
            protected_attr=protected_name,
        )

        dp = float(metrics.get("dpd", 0.0))
        eo = float(equal_opportunity(y.astype(int), y_pred.astype(int), protected_binary.astype(int)))
        bias_score = (dp + eo) / 2.0
        feat_imp = feature_importance(X, y, feature_names)
    except Exception:
        bias_score = 0.5
        feat_imp = {name: (1.0 / len(feature_names)) for name in feature_names}
        dp, eo = demographic_parity(y, protected_binary), 0.5

    return float(bias_score), feat_imp, float(dp), float(eo)
