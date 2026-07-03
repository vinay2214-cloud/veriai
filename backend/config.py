'''backend/config.py'''
"""Configuration module for VeriAI backend.
Defines constants for trust score weighting, database path, and other
runtime settings. Centralizing these values makes it easy to swap
components (e.g., replace SQLite with Firestore) without touching the
service logic.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
# SQLite file stored in the project root for local development.
# On Render, prefer VERIAI_DB_PATH on a persistent disk (for example
# /var/data/veriai.db); otherwise fall back to /tmp on read-only filesystems.
BASE_DIR = Path(__file__).resolve().parent.parent
_default_db = str(BASE_DIR / "veriai.db")

def _resolve_db_path() -> str:
    """Return a writable SQLite path."""
    explicit = os.getenv("VERIAI_DB_PATH", "").strip()
    if explicit:
        path = Path(explicit)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return explicit
    # Check if project root is writable
    try:
        test_file = BASE_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        return _default_db
    except OSError:
        # Read-only filesystem (Render free tier) — use /tmp
        return "/tmp/veriai.db"

DB_PATH = _resolve_db_path()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _split_csv_env(name: str, default: str = "", fallback_name: str | None = None) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw and fallback_name:
        raw = os.getenv(fallback_name, "").strip()
    if not raw:
        raw = default
    return [item.strip() for item in raw.split(",") if item.strip()]


CORS_ORIGINS = _split_csv_env(
    "VERIAI_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8000,http://127.0.0.1:8000,"
    "https://veriai-eyxl.onrender.com",
    fallback_name="ALLOWED_ORIGINS",
)

# ---------------------------------------------------------------------------
# Render / demo storage guardrails
# ---------------------------------------------------------------------------
# Public uploads are processed in memory only. These limits keep the demo
# responsive and prevent accidental large-file pressure on Render instances.
MAX_PUBLIC_UPLOAD_MB = int(os.getenv("MAX_PUBLIC_UPLOAD_MB", os.getenv("MAX_FILE_SIZE_MB", "5")))
MAX_PUBLIC_UPLOAD_ROWS = int(os.getenv("MAX_PUBLIC_UPLOAD_ROWS", "5000"))
PUBLIC_UPLOAD_PREVIEW_ROWS = int(os.getenv("PUBLIC_UPLOAD_PREVIEW_ROWS", "5"))

# SQLite pruning keeps the persistent demo database bounded. The values are
# intentionally small enough for a public jury demo while preserving useful
# dashboards and report history.
MAX_AUDIT_RECORDS = int(os.getenv("MAX_AUDIT_RECORDS", "75"))
MAX_REVIEW_RECORDS = int(os.getenv("MAX_REVIEW_RECORDS", "100"))
MAX_FEEDBACK_RECORDS = int(os.getenv("MAX_FEEDBACK_RECORDS", "200"))
MAX_KB_ARTICLES = int(os.getenv("MAX_KB_ARTICLES", "75"))
MAX_REPORT_JSON_CHARS = int(os.getenv("MAX_REPORT_JSON_CHARS", "18000"))


def get_async_database_url() -> str:
    """Return async SQLAlchemy DB URL.
    Supports Render-style `postgres://...` and normalizes it to asyncpg.
    Falls back to local SQLite for development.
    """
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            return DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        if DATABASE_URL.startswith("postgresql://"):
            return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return DATABASE_URL
    return f"sqlite+aiosqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Trust score weighting (must sum to 1.0)
# ---------------------------------------------------------------------------
TRUST_WEIGHTS = {"truth": 0.40, "bias": 0.40, "confidence": 0.20}

# Mutable runtime weights — API can update these without restarting
CUSTOM_WEIGHTS: dict = {}

# Industry presets for trust formula configurability
INDUSTRY_PRESETS = {
    "general": {
        "label": "General Purpose",
        "description": "Balanced trust scoring for general AI auditing.",
        "weights": {"truth": 0.40, "bias": 0.40, "confidence": 0.20},
    },
    "healthcare": {
        "label": "Healthcare / Medical",
        "description": "Prioritizes factual grounding for medical and clinical claims.",
        "weights": {"truth": 0.45, "bias": 0.35, "confidence": 0.20},
    },
    "finance": {
        "label": "Finance / Banking",
        "description": "Balances truth and fairness for lending and credit decisions.",
        "weights": {"truth": 0.38, "bias": 0.42, "confidence": 0.20},
    },
    "hiring": {
        "label": "HR / Hiring",
        "description": "Prioritizes fairness for screening, ranking, and hiring workflows.",
        "weights": {"truth": 0.35, "bias": 0.45, "confidence": 0.20},
    },
}

def get_active_weights() -> dict:
    """Return the currently active trust weights.
    Uses CUSTOM_WEIGHTS if set, otherwise falls back to TRUST_WEIGHTS.
    """
    return CUSTOM_WEIGHTS if CUSTOM_WEIGHTS else TRUST_WEIGHTS

# ---------------------------------------------------------------------------
# Miscellaneous settings
# ---------------------------------------------------------------------------
# Minimum similarity threshold for RAG source relevance (cosine similarity)
RAG_SIMILARITY_THRESHOLD = 0.6

# Number of clusters for KMeans (can be overridden per request)
DEFAULT_NUM_CLUSTERS = 4

# Logging level – can be overridden via VERIAI_LOG_LEVEL env var
LOG_LEVEL = os.getenv("VERIAI_LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Human-in-the-loop review threshold
# ---------------------------------------------------------------------------
# Audits with trust score below this threshold are flagged for human review
HUMAN_REVIEW_THRESHOLD = float(os.getenv("VERIAI_REVIEW_THRESHOLD", "0.60"))

# ---------------------------------------------------------------------------
# Phase 3 — AI intelligence layer (business/compliance narratives & analytics)
# ---------------------------------------------------------------------------
# Additive constants only. These power the deterministic "AI" services
# (orchestrator / compliance officer / review manager / business metrics) that
# turn raw audit metrics into business output. Nothing here changes the trust
# formula or any existing behavior.

# Estimated analyst time saved per automated audit, in minutes. Basis: a manual
# fairness + factual review of a single model output/dataset by a compliance
# analyst (data prep, metric computation, write-up) is conservatively ~4 hours.
# This is a transparent, configurable ESTIMATE — always surfaced to users as an
# estimate, never presented as a measured fact. Override via env for a customer's
# own baseline.
MANUAL_AUDIT_MINUTES = int(os.getenv("VERIAI_MANUAL_AUDIT_MINUTES", "240"))

# Trust-score bands (0..1) used consistently across the AI narratives, review
# prioritization and executive insights so "risk level" means the same thing
# everywhere. Aligned with the existing HUMAN_REVIEW_THRESHOLD (0.60).
TRUST_BANDS = {
    "critical": 0.50,   # < 0.50  → critical business/compliance risk
    "elevated": 0.60,   # < 0.60  → elevated risk (also the human-review line)
    "moderate": 0.75,   # < 0.75  → moderate risk
    # >= 0.75 → low risk
}

# Named compliance frameworks the AI Compliance Officer maps findings against.
# Metadata only — used to render consistent, consultant-grade compliance mapping.
COMPLIANCE_FRAMEWORKS = {
    "eeoc": {
        "name": "EEOC / Title VII (US employment)",
        "reference": "EEOC §1691, 29 CFR 1607 (four-fifths rule)",
        "domain": "hiring",
    },
    "ecoa": {
        "name": "ECOA / Regulation B (US fair lending)",
        "reference": "ECOA 15 U.S.C. §1691",
        "domain": "finance",
    },
    "eu_ai_act": {
        "name": "EU AI Act (high-risk AI systems)",
        "reference": "Regulation (EU) 2024/1689, Art. 10 (data governance)",
        "domain": "general",
    },
    "nist_ai_rmf": {
        "name": "NIST AI Risk Management Framework",
        "reference": "NIST AI 100-1 (Measure / Manage functions)",
        "domain": "general",
    },
    "gdpr": {
        "name": "GDPR automated decision-making",
        "reference": "Regulation (EU) 2016/679, Art. 22",
        "domain": "general",
    },
    "who": {
        "name": "WHO / clinical safety",
        "reference": "WHO Essential Medicines & clinical-guidance integrity",
        "domain": "healthcare",
    },
}

# ---------------------------------------------------------------------------
# Helper utilities (optional)
# ---------------------------------------------------------------------------
def get_db_path() -> str:
    """Return the absolute path to the SQLite database file.
    Allows callers to respect any runtime overrides.
    """
    return DB_PATH
