"""Explainability service with portability-safe fallbacks.

Priority:
1. SHAP (if installed and method supported)
2. LIME (if installed)
3. Coefficient explanation (always available for linear models)
"""
import time
import numpy as np
import hashlib
import pandas as pd

from .training_service import get_live_model, preprocess_data, load_data

_SHAP_CACHE: dict = {}
_MODEL_VERSION: int = 0


def invalidate_shap_cache():
    global _SHAP_CACHE, _MODEL_VERSION
    _SHAP_CACHE.clear()
    _MODEL_VERSION += 1


def _coefficient_explanation(model, instance_scaled, feature_names):
    coefs = model.coef_[0] if model.coef_.ndim > 1 else model.coef_
    impacts = coefs * instance_scaled[0]
    contributions = []
    for name, val in zip(feature_names, impacts):
        if abs(val) > 0.03:
            contributions.append({"feature": name, "impact": float(val)})
    contributions.sort(key=lambda x: abs(x["impact"]), reverse=True)
    base_value = float(model.intercept_[0]) if hasattr(model.intercept_, "__len__") else float(model.intercept_)
    return base_value, contributions


def _permutation_explanation(model, X_train_scaled, instance_scaled, feature_names):
    try:
        import shap  # type: ignore
    except Exception as exc:
        raise RuntimeError("SHAP is unavailable.") from exc
    sample_size = min(100, X_train_scaled.shape[0])
    background = X_train_scaled[np.random.choice(X_train_scaled.shape[0], sample_size, replace=False)]
    
    predict_fn = getattr(model, "predict_proba", model.predict)
    explainer = shap.Explainer(predict_fn, background, algorithm="permutation")
    shap_values = explainer(instance_scaled)
    
    sv = shap_values.values[0]
    if sv.ndim > 1:
        sv = sv[:, 1]
        
    contributions = []
    for name, val in zip(feature_names, sv):
        if abs(val) > 0.03:
            contributions.append({"feature": name, "impact": float(val)})
    contributions.sort(key=lambda x: abs(x["impact"]), reverse=True)
    
    base = shap_values.base_values[0]
    if isinstance(base, (list, np.ndarray)):
        base = base[-1]
    return float(base), contributions


def _lime_explanation(model, X_train, instance_raw, feature_names):
    try:
        from lime.lime_tabular import LimeTabularExplainer  # type: ignore
    except Exception as exc:
        raise RuntimeError("LIME is unavailable.") from exc
    explainer = LimeTabularExplainer(
        training_data=X_train,
        feature_names=feature_names,
        class_names=["<=50K", ">50K"],
        mode="classification",
        random_state=42,
    )
    explanation = explainer.explain_instance(
        instance_raw[0],
        model.predict_proba,
        num_features=min(8, len(feature_names)),
    )
    contributions = []
    for feature_desc, impact in explanation.as_list():
        contributions.append({"feature": feature_desc, "impact": float(impact)})
    contributions.sort(key=lambda x: abs(x["impact"]), reverse=True)
    base = float(explanation.predict_proba[1]) if hasattr(explanation, "predict_proba") else 0.5
    return base, contributions


def _shap_linear_explanation(model, X_train_scaled, instance_scaled, feature_names):
    try:
        import shap  # type: ignore
    except Exception as exc:
        raise RuntimeError("SHAP is unavailable.") from exc
    sample_size = min(100, X_train_scaled.shape[0])
    background = X_train_scaled[np.random.choice(X_train_scaled.shape[0], sample_size, replace=False)]
    explainer = shap.LinearExplainer(model, background)
    shap_values = explainer.shap_values(instance_scaled)
    sv = shap_values[1][0] if isinstance(shap_values, list) else shap_values[0]
    contributions = []
    for name, val in zip(feature_names, sv):
        if abs(val) > 0.03:
            contributions.append({"feature": name, "impact": float(val)})
    contributions.sort(key=lambda x: abs(x["impact"]), reverse=True)
    expected = explainer.expected_value
    if isinstance(expected, (list, np.ndarray)):
        expected = expected[-1]
    return float(expected), contributions


def _get_dataset_hash(df: pd.DataFrame) -> str:
    """Compute a simple dataset hash."""
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values).hexdigest()


def generate_shap_explanation(index: int = 0, method: str = "linear") -> dict:
    try:
        model, scaler = get_live_model()
        df = load_data()
        
        # Cache SHAP results by dataset hash
        dataset_hash = _get_dataset_hash(df)
        cache_key = f"{_MODEL_VERSION}:{dataset_hash}:{method}:{index}"
        
        if cache_key in _SHAP_CACHE:
            cached = dict(_SHAP_CACHE[cache_key])
            cached["from_cache"] = True
            return cached
        X_raw, _y, feature_names = preprocess_data(df)
        if index < 0 or index >= len(X_raw):
            return {"status": "error", "message": f"Index out of range. Got {index}, max is {len(X_raw) - 1}."}

        instance_raw = X_raw[index:index + 1]
        instance_scaled = scaler.transform(instance_raw)
        X_scaled = scaler.transform(X_raw)

        t0 = time.time()
        used_method = method

        if method == "coefficient":
            try:
                base_value, contributions = _coefficient_explanation(model, instance_scaled, feature_names)
            except Exception:
                try:
                    base_value, contributions = _permutation_explanation(model, X_scaled, instance_scaled, feature_names)
                    used_method = "permutation (fallback)"
                except Exception:
                    base_value, contributions = _lime_explanation(model, X_raw, instance_raw, feature_names)
                    used_method = "lime (fallback)"
        elif method == "lime":
            try:
                base_value, contributions = _lime_explanation(model, X_raw, instance_raw, feature_names)
            except Exception:
                used_method = "coefficient (fallback)"
                base_value, contributions = _coefficient_explanation(model, instance_scaled, feature_names)
        elif method == "permutation":
            try:
                base_value, contributions = _permutation_explanation(model, X_scaled, instance_scaled, feature_names)
            except Exception:
                try:
                    base_value, contributions = _lime_explanation(model, X_raw, instance_raw, feature_names)
                    used_method = "lime (fallback)"
                except Exception:
                    used_method = "coefficient (fallback)"
                    base_value, contributions = _coefficient_explanation(model, instance_scaled, feature_names)
        else:
            try:
                base_value, contributions = _shap_linear_explanation(model, X_scaled, instance_scaled, feature_names)
                used_method = "shap-linear"
            except Exception:
                try:
                    base_value, contributions = _lime_explanation(model, X_raw, instance_raw, feature_names)
                    used_method = "lime (fallback)"
                except Exception:
                    used_method = "coefficient (fallback)"
                    base_value, contributions = _coefficient_explanation(model, instance_scaled, feature_names)

        result = {
            "status": "success",
            "base_value": float(base_value),
            "contributions": contributions[:8],
            "person_index": index,
            "method": used_method,
            "computation_time": round(time.time() - t0, 3),
            "from_cache": False,
        }
        _SHAP_CACHE[cache_key] = dict(result)
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
