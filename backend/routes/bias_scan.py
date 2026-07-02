"""Standalone bias‑scan endpoint.
Accepts dataset input and returns bias metrics without running the full pipeline.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import numpy as np

from ..services.bias_service import compute_bias_score

router = APIRouter()


class BiasScanRequest(BaseModel):
    data: str = Field(..., description="JSON string with features, labels, feature_names, protected_index")


@router.post("/bias-scan")
async def bias_scan(request: BiasScanRequest):
    """Run bias analysis only."""
    try:
        parsed = json.loads(request.data)
        if not isinstance(parsed, dict):
            raise ValueError("Payload must be a JSON object.")
        if "features" not in parsed or "labels" not in parsed:
            raise ValueError("Payload must include 'features' and 'labels'.")
        X = np.array(parsed["features"], dtype=float)
        y = np.array(parsed["labels"], dtype=float)
        if X.ndim != 2:
            raise ValueError("'features' must be a 2D array.")
        if y.ndim != 1:
            raise ValueError("'labels' must be a 1D array.")
        if len(X) != len(y):
            raise ValueError("Features and labels must have the same row count.")
        names = parsed.get("feature_names", [f"f{i}" for i in range(X.shape[1])])
        prot_idx = int(parsed.get("protected_index", 0))
        if prot_idx < 0 or prot_idx >= X.shape[1]:
            raise ValueError("'protected_index' is out of bounds.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        bias_score, feat_imp, dp, eo = compute_bias_score(X, y, prot_idx, names)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bias computation failed: {exc}")
    return {
        "bias_score": round(bias_score, 4),
        "demographic_parity": round(dp, 4),
        "equalized_odds": round(eo, 4),
        "feature_importance": {k: round(v, 4) for k, v in feat_imp.items()},
    }
