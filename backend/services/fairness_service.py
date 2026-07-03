"""Fairness detection utilities.
Provides Demographic Parity and Equal Opportunity metrics.
"""
import numpy as np
# sklearn.metrics.confusion_matrix is imported lazily inside equal_opportunity
# (Phase 2 startup optimization).
from .training_service import load_model, get_live_model, preprocess_data, load_data

def demographic_parity(y_pred: np.ndarray, protected: np.ndarray) -> float:
    """Calculate absolute difference in positive prediction rates between protected groups."""
    group0_rate = y_pred[protected == 0].mean() if (protected == 0).sum() > 0 else 0.0
    group1_rate = y_pred[protected == 1].mean() if (protected == 1).sum() > 0 else 0.0
    return abs(group0_rate - group1_rate)

def equal_opportunity(y_true: np.ndarray, y_pred: np.ndarray, protected: np.ndarray) -> float:
    """Calculate the absolute difference in true positive rates (Recall) across protected groups."""
    from sklearn.metrics import confusion_matrix

    def tpr(mask):
        if mask.sum() == 0:
            return 0.0
        # confusion_matrix with labels=[0,1] ensures a 2x2 matrix
        tn, fp, fn, tp = confusion_matrix(y_true[mask], y_pred[mask], labels=[0, 1]).ravel()
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    tpr0 = tpr(protected == 0)
    tpr1 = tpr(protected == 1)
    return abs(tpr0 - tpr1)

def compute_real_fairness() -> dict:
    """Compute Demographic Parity and Equal Opportunity metrics on the dataset using the deployed model."""
    try:
        model, scaler = get_live_model()
        df = load_data()
        
        if "sex" not in df.columns:
            return {"error": "Required protected attribute 'sex' not found."}
            
        X_encoded, y_true, _ = preprocess_data(df)
        X_scaled = scaler.transform(X_encoded)
        y_pred = model.predict(X_scaled)
        
        # Male = 0, Female = 1 for disparity calculation masking
        protected = np.where(df['sex'].str.strip() == "Female", 1, 0)
        
        dp = demographic_parity(y_pred, protected)
        eq_opp = equal_opportunity(y_true, y_pred, protected)
        
        return {
            "demographic_parity": float(dp),
            "equal_opportunity": float(eq_opp)
        }
    except FileNotFoundError:
        return {"error": "Model or dataset not found. Please train the model first."}
    except Exception as e:
        return {"error": str(e)}
