"""Public demo dataset endpoints."""
from fastapi import APIRouter, HTTPException

from ..seed_data import SAMPLE_AUDIT

router = APIRouter()

# PUBLIC: NO AUTH REQUIRED FOR JURY
DEMO_DATASETS = {
    "hiring-bias-demo": {
        "key": "hiring-bias-demo",
        "name": "Hiring Bias Demo Dataset",
        "description": "Pre-loaded demo scenario for jury evaluation.",
        "audit_id": SAMPLE_AUDIT["id"],
    }
}

DEMO_RESULTS = {
    "hiring-bias-demo": {
        "audit_id": SAMPLE_AUDIT["id"],
        "input": SAMPLE_AUDIT["input"],
        "bias_score": SAMPLE_AUDIT["bias_score"],
        "truth_score": SAMPLE_AUDIT["truth_score"],
        "trust_score": SAMPLE_AUDIT["trust_score"],
        "corrected": SAMPLE_AUDIT["corrected"],
        "reasoning_steps": [],
    }
}


@router.get("/demo/datasets")
async def list_demo_datasets():
    return {"datasets": list(DEMO_DATASETS.values())}


@router.get("/demo/datasets/{key}/results")
async def get_demo_dataset_results(key: str):
    result = DEMO_RESULTS.get(key)
    if not result:
        raise HTTPException(status_code=404, detail=f"Demo dataset '{key}' not found")
    return result

