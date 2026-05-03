"""PII redaction utilities for datasets sent to GCP services."""
from __future__ import annotations

import re

import pandas as pd

_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)")


def _redact_text(value: str) -> str:
    if not value:
        return value
    redacted = _EMAIL_RE.sub("[REDACTED]", value)
    redacted = _SSN_RE.sub("[REDACTED]", redacted)
    redacted = _PHONE_RE.sub("[REDACTED]", redacted)
    return redacted


def redact_for_gcp(df: pd.DataFrame, *, is_demo: bool = False) -> pd.DataFrame:
    """Redact common PII patterns before sending private data to Gemini/Vertex AI.

    Demo datasets are intentionally skipped.
    """
    if is_demo or df is None or df.empty:
        return df

    redacted_df = df.copy(deep=True)
    for col_name in redacted_df.columns:
        redacted_df[col_name] = redacted_df[col_name].map(
            lambda value: _redact_text(value) if isinstance(value, str) else value
        )
    return redacted_df

