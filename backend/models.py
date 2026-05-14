"""Pydantic schemas used by the FastAPI endpoints.
All request/response bodies are defined here to keep the API contract
clear and type‑safe.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Core request/response models
# ---------------------------------------------------------------------------
class AuditRequest(BaseModel):
    """Payload for a full audit.
    `input_text` can be raw text, a JSON‑encoded dataset, or model output.
    """
    input_text: Optional[str] = Field(None, description="Raw text or JSON string to audit")
    dataset_id: Optional[str] = Field(None, description="Optional demo/private dataset identifier")
    features: Optional[Any] = Field(None, description="Optional numeric feature matrix or feature names")
    labels: Optional[List[Any]] = Field(None, description="Optional numeric/binary labels for structured dataset audit")
    feature_names: Optional[List[str]] = Field(None, description="Optional names for structured dataset features")
    protected_index: Optional[int] = Field(0, description="Protected feature index for structured dataset audit")
    target_column: Optional[str] = Field(None, description="Optional target column name from UI/API clients")
    protected_attributes: Optional[List[str]] = Field(
        None, description="Names of protected attributes for bias analysis"
    )
    audit_options: Optional[Dict[str, Any]] = Field(None, description="Optional client audit settings")
    num_clusters: Optional[int] = Field(4, description="KMeans clusters for analysis")
    depth: Optional[str] = Field("standard", description="Audit depth: 'fast', 'standard', or 'thorough'")

class BiasReport(BaseModel):
    bias_score: float = Field(..., ge=0.0, le=1.0, description="Overall bias score (0‑1)")
    demographic_parity: float = Field(..., description="DP metric")
    equalized_odds: float = Field(..., description="EO metric")
    feature_importance: Dict[str, float] = Field(..., description="SHAP‑like importance per feature")

class TruthReport(BaseModel):
    truth_score: float = Field(..., ge=0.0, le=1.0, description="Truthfulness score (0‑1)")
    groundedness: float = Field(..., description="Cosine similarity to sources")
    citations: List[Dict[str, Any]] = Field(..., description="List of source dicts {title, url, snippet}")

class ClusterReport(BaseModel):
    cluster_fairness: float = Field(..., description="Fairness across clusters")
    cluster_details: List[Dict[str, Any]] = Field(..., description="Per‑cluster bias info")

class DistributionReport(BaseModel):
    distribution_stability: float = Field(..., description="Stability metric (0‑1)")
    stats: Dict[str, float] = Field(..., description="Mean, std, skewness, kurtosis")

class AuditResult(BaseModel):
    audit_id: str
    input_text: str
    bias: BiasReport
    truth: TruthReport
    cluster: ClusterReport
    distribution: DistributionReport
    trust_score: float = Field(..., description="Weighted trust score")
    corrections: Optional[str] = Field(None, description="Corrected output if any")
    reasoning_steps: List[Dict[str, Any]] = Field(..., description="Log of each reasoning step")

class FeedbackEntry(BaseModel):
    audit_id: str
    correct: bool = Field(..., description="Was the corrected output satisfactory?")
    bias_flag: bool = Field(..., description="Did the user notice remaining bias?")
    notes: Optional[str] = Field("", description="Additional comments")

class FeedbackResponse(BaseModel):
    status: str = Field(..., description="Result of storing feedback")

class DashboardStats(BaseModel):
    total_audits: int
    avg_trust: float
    recent_audits: List[Dict[str, Any]]

# ---------------------------------------------------------------------------
# Helper response models for simple endpoints
# ---------------------------------------------------------------------------
class SimpleScoreResponse(BaseModel):
    score: float
    details: Dict[str, Any]

class ReportResponse(BaseModel):
    audit: AuditResult

# End of models.py
