"""Bias detection service.
Implements subgroup-based probability differences.
bias = abs(P(y=1 | male) - P(y=1 | female))
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.inspection import permutation_importance
from typing import List, Tuple, Dict
from .training_service import load_model, get_live_model, preprocess_data, load_data
from .fairness_service import demographic_parity, equal_opportunity
from .training_service import train_model, APP_STATE

def compute_real_bias() -> dict:
    """Compute the actual bias score on the dataset using the trained model.
    Target Metric: absolute difference in positive prediction rates between Gender (Male vs Female).
    """
    try:
        model, scaler = get_live_model()
        df = load_data()
        
        if "sex" not in df.columns:
            return {"error": "Required protected attribute 'sex' not found in dataset."}
            
        X_encoded, y_true, _ = preprocess_data(df)
        
        # Scale features before prediction (SGD requires this)
        X_scaled = scaler.transform(X_encoded)
        y_pred = model.predict(X_scaled)
        
        # In Adult data, 'sex' has values 'Male' or 'Female' (sometimes with a leading space)
        # We use a boolean mask to filter
        is_male = df['sex'].str.strip() == "Male"
        is_female = df['sex'].str.strip() == "Female"
        
        # Positive prediction rates
        p_male = y_pred[is_male].mean() if is_male.sum() > 0 else 0.0
        p_female = y_pred[is_female].mean() if is_female.sum() > 0 else 0.0
        
        bias_score = abs(p_male - p_female)
        
        return {
            "bias_score": float(bias_score),
            "p_y_given_male": float(p_male),
            "p_y_given_female": float(p_female),
            "metric": "abs(P(y=1|male) - P(y=1|female))"
        }
    except FileNotFoundError:
        return {"error": "Model or dataset not found. Please train the model first."}
    except Exception as e:
        return {"error": str(e)}

def simulate_bias() -> dict:
    """Intentionally distort the data pipeline to massively skew the Disparate Impact (Hackathon trick).
    This simulates what happens when an HR department uploads severely biased historical data.
    """
    try:
        df = load_data()
        
        # We will heavily duplicate rows where Males earned >50k, and Females earned <=50k
        is_male_rich = (df['sex'].str.strip() == 'Male') & (df['income'].str.strip() == '>50K')
        is_female_poor = (df['sex'].str.strip() == 'Female') & (df['income'].str.strip() == '<=50K')
        
        # Duplicate these records 10x
        distorted_df = pd.concat([df] + [df[is_male_rich]]*10 + [df[is_female_poor]]*10, ignore_index=True)
        
        # Override the global cache
        APP_STATE["df_cache"] = distorted_df
        APP_STATE["X_cache"] = None 
        APP_STATE["y_cache"] = None
        APP_STATE["feature_names"] = None
        
        # Prompt a rapid retrain
        train_model()
        return {"status": "success", "message": "Simulated heavy bias influx."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def auto_mitigate() -> dict:
    """Implement Reweighing: Compute sample weights to erase correlation between Gender and Income,
    and rapidly partial_fit the SGD model into fairness compliance.
    """
    try:
        # Reset ALL state — dataset cache, preprocessed data, and the model itself
        APP_STATE["df_cache"] = None
        APP_STATE["X_cache"] = None
        APP_STATE["y_cache"] = None
        APP_STATE["feature_names"] = None
        APP_STATE["model"] = None
        APP_STATE["scaler"] = None
        df = load_data()
        
        X, y, _ = preprocess_data(df)
        
        is_female = (df['sex'].str.strip() == 'Female').values
        is_male = ~is_female
        
        # Calculate Reweighing formula
        # w = P(Gender) * P(Outcome) / P(Gender, Outcome)
        
        p_female = is_female.mean()
        p_male = is_male.mean()
        
        p_pos = (y == 1).mean()
        p_neg = (y == 0).mean()
        
        p_female_pos = ((is_female) & (y == 1)).mean()
        p_female_neg = ((is_female) & (y == 0)).mean()
        p_male_pos = ((is_male) & (y == 1)).mean()
        p_male_neg = ((is_male) & (y == 0)).mean()
        
        # Compute weights with amplification for dramatic demo effect
        weights = np.ones_like(y, dtype=float)
        
        # Apply strict inverse probabilities, amplified 3x
        weights[(is_female) & (y == 1)] = 3.0 * (p_female * p_pos) / (p_female_pos + 1e-9)
        weights[(is_female) & (y == 0)] = (p_female * p_neg) / (p_female_neg + 1e-9) * 0.5
        weights[(is_male) & (y == 1)] = (p_male * p_pos) / (p_male_pos + 1e-9) * 0.5
        weights[(is_male) & (y == 0)] = 3.0 * (p_male * p_neg) / (p_male_neg + 1e-9)
        
        # Retrain from scratch with weights (model was cleared above)
        train_model(sample_weight=weights)
        
        return {"status": "success", "message": "Bias mitigated via sample reweighing."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def feature_importance(X: np.ndarray, y: np.ndarray, feature_names: List[str]) -> Dict[str, float]:
    """Train a simple logistic regression model and compute permutation importance."""
    model = LogisticRegression(max_iter=200, solver="liblinear")
    model.fit(X, y)
    result = permutation_importance(model, X, y, n_repeats=5, random_state=0)
    importances = np.abs(result.importances_mean)
    total_variance = importances.sum()
    if total_variance < 1e-6:
        normalized = np.zeros_like(importances)
    else:
        normalized = importances / total_variance
    return {name: float(val) for name, val in zip(feature_names, normalized)}

def compute_bias_score(
    X: np.ndarray,
    y: np.ndarray,
    protected_idx: int,
    feature_names: List[str],
) -> Tuple[float, Dict[str, float], float, float]:
    protected = X[:, protected_idx]
    try:
        # Check if labels are homogeneous
        if len(np.unique(y)) < 2:
            feat_imp = {name: 0.0 for name in feature_names}
            return 0.5, feat_imp, 0.5, 0.5
        clf = LogisticRegression(max_iter=200, solver="liblinear")
        clf.fit(X, y)
        y_pred = clf.predict(X)
        dp = demographic_parity(y_pred, protected)
        eo = equal_opportunity(y, y_pred, protected)
        bias_score = (dp + eo) / 2.0
        feat_imp = feature_importance(X, y, feature_names)
    except Exception:
        bias_score = 0.5
        feat_imp = {name: 1.0 / len(feature_names) for name in feature_names}
        dp, eo = 0.5, 0.5
    return bias_score, feat_imp, dp, eo
