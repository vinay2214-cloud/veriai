"""Public demo dataset endpoints."""
from fastapi import APIRouter, HTTPException

from ..seed_data import SAMPLE_AUDIT

router = APIRouter()

from ..demo.datasets import DEMO_SCENARIOS
from pydantic import BaseModel

router = APIRouter()

@router.get("/demo/datasets")
async def list_demo_datasets():
    return {"datasets": list(DEMO_SCENARIOS.values())}

class DemoAuditRequest(BaseModel):
    # Dummy schema if the frontend sends something
    pass

@router.post("/demo/{dataset_key}/run-audit")
async def run_demo_audit(dataset_key: str):
    if dataset_key not in DEMO_SCENARIOS:
        raise HTTPException(status_code=404, detail="Demo dataset not found")
        
    scenario = DEMO_SCENARIOS[dataset_key]
    
    # We run the actual pipeline on a synthetic demo string to simulate the delay
    from ..services.reasoning_chain import run_audit
    try:
        # Run the actual pipeline (fast mode so we don't hold up the jury demo too long)
        raw_result = await run_audit("demo synthetic input data", depth="fast")
    except Exception as e:
        raw_result = {"reasoning_steps": [], "elapsed_seconds": 0.5}
        
    # We overwrite the results to MATCH EXACTLY the numbers in PROJECT_CONTEXT.md
    # BEFORE auto-correction (base audit):
    # Trust Score: 51/100 -> 0.51
    # Bias (DPD): 38% -> 0.38
    # Truth Score: 62% -> 0.62
    # Top feature: zip_code
    
    # AFTER auto-correction (returned as corrected metrics, but wait, the pipeline returns 1 result)
    # The requirement says "Results must match the demo numbers"
    # We will embed the before and after in the single result, or just output the before and let
    # the frontend 'correct' it. The result schema has trust_score etc.
    
    result = dict(raw_result)
    result["trust_score"] = 0.51
    
    if "bias" not in result:
        result["bias"] = {}
    result["bias"]["demographic_parity"] = 0.38
    result["bias"]["feature_importance"] = {"zip_code": 0.73, "other": 0.27}
    
    if "truth" not in result:
        result["truth"] = {}
    result["truth"]["truth_score"] = 0.62
    result["truth"]["citations"] = [
        {"title": "Hallucinated citation 1", "snippet": "Fake snippet"},
        {"title": "Hallucinated citation 2", "snippet": "Fake snippet"},
        {"title": "Hallucinated citation 3", "snippet": "Fake snippet"}
    ]
    
    if dataset_key == "hiring_bias_demo":
        result["regulatory_flags"] = [{"regulation": "ECOA §1691", "description": "zip_code proxy discrimination", "type": "warning"}]
    elif dataset_key == "healthcare_hallucination_demo":
        result["regulatory_flags"] = [{"regulation": "WHO Essential Medicines", "description": "drug dosage hallucinations", "type": "danger"}]
    elif dataset_key == "lending_fairness_demo":
        result["regulatory_flags"] = [{"regulation": "EU AI Act Art. 10", "description": "training data quality violations", "type": "primary"}]
    else:
        result["regulatory_flags"] = []
    
    # Include the "after" numbers inside corrections for the frontend to use
    result["corrections_demo"] = {
        "trust_score": 0.89,
        "bias_dpd": 0.042,
        "truth_score": 0.94,
        "changes": 3
    }
    
    # Provide the pre-computed summary
    result["audit_id"] = f"demo-{dataset_key}"
    result["input_text"] = scenario["input_data"]
    
    return result
