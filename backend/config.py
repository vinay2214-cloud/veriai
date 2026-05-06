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


def _split_csv_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


CORS_ORIGINS = _split_csv_env(
    "VERIAI_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8000,http://127.0.0.1:8000,"
    "https://veriai-eyxl.onrender.com",
)


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
TRUST_WEIGHTS = {
    "truth": 0.35,
    "bias": 0.30,          # note: we use (1 - bias_score) in the formula
    "confidence": 0.15,
    "cluster": 0.10,
    "distribution": 0.10,
}

# Mutable runtime weights — API can update these without restarting
CUSTOM_WEIGHTS: dict = {}

# Industry presets for trust formula configurability
INDUSTRY_PRESETS = {
    "general": {
        "label": "General Purpose",
        "description": "Balanced weights for general AI auditing",
        "weights": {"truth": 0.35, "bias": 0.30, "confidence": 0.15, "cluster": 0.10, "distribution": 0.10},
    },
    "healthcare": {
        "label": "Healthcare / Medical",
        "description": "Heavy truth weighting — medical claims must be factually grounded",
        "weights": {"truth": 0.45, "bias": 0.25, "confidence": 0.15, "cluster": 0.10, "distribution": 0.05},
    },
    "finance": {
        "label": "Finance / Banking",
        "description": "Bias-heavy — loan and credit scoring must be demographically fair",
        "weights": {"truth": 0.30, "bias": 0.35, "confidence": 0.15, "cluster": 0.10, "distribution": 0.10},
    },
    "hiring": {
        "label": "HR / Hiring",
        "description": "Maximum bias sensitivity — hiring decisions must not discriminate",
        "weights": {"truth": 0.25, "bias": 0.40, "confidence": 0.15, "cluster": 0.10, "distribution": 0.10},
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
# Helper utilities (optional)
# ---------------------------------------------------------------------------
def get_db_path() -> str:
    """Return the absolute path to the SQLite database file.
    Allows callers to respect any runtime overrides.
    """
    return DB_PATH
