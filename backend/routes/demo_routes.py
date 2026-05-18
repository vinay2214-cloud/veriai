from fastapi import APIRouter

from backend.demo.sample_datasets import (
    generate_hiring_bias_dataset,
    generate_lending_bias_dataset,
)

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/datasets")
async def list_demo_datasets():
    """Public endpoint — no auth. Lists available demo datasets."""
    return [
        {
            "id": "hiring_bias_demo",
            "name": "Hiring Bias Demo",
            "description": "1000-row synthetic hiring dataset with measurable gender bias",
            "use_case": "hiring",
            "rows": 1000,
            "protected_attribute": "gender",
            "label_column": "hired",
            "expected_bias_dpd": 0.22,
        },
        {
            "id": "lending_bias_demo",
            "name": "Lending Fairness Demo",
            "description": "1500-row credit scoring dataset with racial proxy bias",
            "use_case": "finance",
            "rows": 1500,
            "protected_attribute": "race",
            "label_column": "loan_approved",
            "expected_bias_dpd": 0.41,
        },
    ]


@router.post("/datasets/{dataset_id}/run-audit")
async def run_demo_audit(dataset_id: str):
    """
    Public endpoint — no auth required.
    Runs real bias detection on synthetic demo data.
    """
    from backend.services.reasoning_chain import run_full_pipeline

    if dataset_id == "hiring_bias_demo":
        df = generate_hiring_bias_dataset()
        config = {
            "features": ["age", "education", "years_experience", "zip_code"],
            "target_column": "hired",
            "protected_attributes": ["gender"],
            "use_case": "hiring",
        }
    elif dataset_id == "lending_bias_demo":
        df = generate_lending_bias_dataset()
        config = {
            "features": ["income", "credit_score", "neighborhood_score"],
            "target_column": "loan_approved",
            "protected_attributes": ["race"],
            "use_case": "finance",
        }
    else:
        return {"error": f"Unknown demo dataset: {dataset_id}"}

    result = await run_full_pipeline(df=df, **config)

    from backend.services.scoring_service import compute_trust_score

    truth = float(result.get("truth", {}).get("truth_score", 0.0))
    dpd = float(result.get("bias", {}).get("demographic_parity_difference", 0.0))
    cluster = float(result.get("cluster", {}).get("cluster_fairness", 0.5))
    distribution = float(result.get("distribution", {}).get("distribution_stability", 0.5))
    pre_correction = compute_trust_score(
        truth=truth,
        bias=dpd,
        confidence=0.85,
        cluster=cluster,
        distribution=distribution,
    )["trust_score"]

    post_correction = float(result.get("trust_score", pre_correction))
    result["pre_correction_trust_score"] = round(pre_correction, 4)
    result["post_correction_trust_score"] = round(post_correction, 4)
    result["trust_delta"] = round(post_correction - pre_correction, 4)
    result["trust_score"] = round(pre_correction, 4)
    return result
