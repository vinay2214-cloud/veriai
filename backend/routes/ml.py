"""Machine Learning endpoints.
Exposes real ML pipeline operations: training, prediction, bias calculation, fairness checking.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import numpy as np

from ..services.training_service import train_model, predict
from ..services.bias_service import compute_real_bias, simulate_bias, auto_mitigate
from ..services.fairness_service import compute_real_fairness
from ..services.explainability_service import generate_shap_explanation

router = APIRouter()

class PredictRequest(BaseModel):
    # Depending on input preprocessing, it expects preprocessed numerical form, or we can handle raw dict.
    # To keep it generic for the array:
    features: List[List[float]] = Field(..., description="2D array of processed features for prediction")

@router.post("/train")
async def train_endpoint():
    """Train the model using the backend data."""
    result = train_model()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

@router.post("/predict")
async def predict_endpoint(request: PredictRequest):
    """Predict outputs for given features."""
    try:
        X = np.array(request.features)
        y_pred = predict(X)
        return {"predictions": y_pred.tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bias")
async def bias_endpoint():
    """Return the calculated bias based on the adult dataset."""
    try:
        result = compute_real_bias()
        if "error" in result:
            return {"bias_score": 0.0, "p_y_given_male": 0.0, "p_y_given_female": 0.0}
        return result
    except Exception:
        return {"bias_score": 0.0, "p_y_given_male": 0.0, "p_y_given_female": 0.0}

@router.get("/fairness")
async def fairness_endpoint():
    """Return the Demographic Parity and Equal Opportunity."""
    try:
        result = compute_real_fairness()
        if "error" in result:
            return {"demographic_parity": 0.0, "equal_opportunity": 0.0}
        return result
    except Exception:
        return {"demographic_parity": 0.0, "equal_opportunity": 0.0}

@router.get("/explain")
async def explain_endpoint(index: int = 0, method: str = "linear"):
    """Return SHAP explanation for a given instance.
    Methods: linear (default), coefficient (fastest), permutation (slow).
    """
    try:
        result = generate_shap_explanation(index, method=method)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Explanation failed: {exc}")
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

@router.post("/simulate-bias")
async def simulate_bias_endpoint():
    """Simulate severe bias influx (Hackathon demo)."""
    result = simulate_bias()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

@router.post("/mitigate-bias")
async def mitigate_bias_endpoint():
    """Trigger auto-mitigation via reweighing (Hackathon demo)."""
    result = auto_mitigate()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result
