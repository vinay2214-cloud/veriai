"""Pre-loaded demo datasets for VeriAI."""

DEMO_SCENARIOS = {
    "hiring-bias": {
        "key": "hiring-bias",
        "name": "Hiring Bias",
        "description": "Resume screening algorithm favoring certain demographics.",
        "input_data": "Synthetic HR dataset with 50,000 applicant records.",
        "pre_computed": {
            "trust_score": 51,
            "bias_dpd": 38,
            "truth_score": 62,
            "top_feature": "zip_code",
            "reg_flag": "ECOA §1691 violation",
        }
    },
    "healthcare-hallucination": {
        "key": "healthcare-hallucination",
        "name": "Healthcare Hallucination",
        "description": "Medical LLM hallucinating drug interactions.",
        "input_data": "Synthetic medical query logs and LLM responses.",
        "pre_computed": {
            "trust_score": 51,
            "bias_dpd": 38,
            "truth_score": 62,
            "top_feature": "zip_code",
            "reg_flag": "WHO Essential Medicines violation",
        }
    },
    "lending-fairness": {
        "key": "lending-fairness",
        "name": "Lending Fairness",
        "description": "Mortgage approval model analyzing applicant zip codes.",
        "input_data": "Synthetic loan application dataset.",
        "pre_computed": {
            "trust_score": 51,
            "bias_dpd": 38,
            "truth_score": 62,
            "top_feature": "zip_code",
            "reg_flag": "ECOA §1691 violation",
        }
    }
}
