"""Settings API — Trust Formula Configuration.
Allows runtime configuration of trust weights and industry presets.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Optional

from ..config import TRUST_WEIGHTS, CUSTOM_WEIGHTS, INDUSTRY_PRESETS, get_active_weights
import backend.config as config

router = APIRouter()


class WeightsUpdate(BaseModel):
    truth: float = Field(..., ge=0.0, le=1.0)
    bias: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)


class PresetRequest(BaseModel):
    preset: str = Field(..., description="Preset name: general, healthcare, finance, hiring")


@router.get("/settings/weights")
async def get_weights():
    """Return current active weights and available industry presets."""
    return {
        "active_weights": get_active_weights(),
        "defaults": TRUST_WEIGHTS,
        "is_custom": bool(config.CUSTOM_WEIGHTS),
        "presets": {
            k: {"label": v["label"], "description": v["description"], "weights": v["weights"]}
            for k, v in INDUSTRY_PRESETS.items()
        },
    }


@router.post("/settings/weights")
async def update_weights(weights: WeightsUpdate):
    """Update trust formula weights at runtime. Weights must sum to ~1.0."""
    w = weights.model_dump()
    total = sum(w.values())
    
    # Allow small floating point tolerance
    if abs(total - 1.0) > 0.02:
        raise HTTPException(
            status_code=400,
            detail=f"Weights must sum to 1.0 (got {total:.4f}). Please adjust values.",
        )
    
    # Normalize to exactly 1.0
    normalized = {k: round(v / total, 4) for k, v in w.items()}
    
    # Update the mutable runtime config
    config.CUSTOM_WEIGHTS.clear()
    config.CUSTOM_WEIGHTS.update(normalized)
    
    return {
        "status": "success",
        "message": "Trust weights updated successfully.",
        "active_weights": get_active_weights(),
    }


@router.post("/settings/weights/preset")
async def apply_preset(request: PresetRequest):
    """Apply an industry preset to the trust formula."""
    preset_name = request.preset.lower()
    
    if preset_name not in INDUSTRY_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset '{preset_name}'. Available: {list(INDUSTRY_PRESETS.keys())}",
        )
    
    preset = INDUSTRY_PRESETS[preset_name]
    
    # Apply preset weights
    config.CUSTOM_WEIGHTS.clear()
    if preset_name != "general":
        config.CUSTOM_WEIGHTS.update(preset["weights"])
    # For "general", clearing CUSTOM_WEIGHTS falls back to TRUST_WEIGHTS defaults
    
    return {
        "status": "success",
        "message": f"Applied '{preset['label']}' preset.",
        "active_weights": get_active_weights(),
    }


@router.post("/settings/weights/reset")
async def reset_weights():
    """Reset trust weights to defaults."""
    config.CUSTOM_WEIGHTS.clear()
    return {
        "status": "success",
        "message": "Trust weights reset to defaults.",
        "active_weights": get_active_weights(),
    }
