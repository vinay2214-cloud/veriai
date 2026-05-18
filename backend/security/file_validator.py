import os
import re
import hashlib
from pathlib import Path
from typing import NamedTuple, Any

import pandas as pd
from fastapi import UploadFile, HTTPException

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
MAX_BYTES = int(os.environ.get("MAX_FILE_SIZE_MB", 10)) * 1024 * 1024
CHUNK = 65536


class ValidationResult(NamedTuple):
    original_filename: str
    safe_filename: str
    extension: str
    size_bytes: int
    sha256: str


async def validate_upload(file: UploadFile) -> ValidationResult:
    """
    Lightweight validation for hackathon.
    Production adds: libmagic MIME detection, injection scanning,
    formula cell sanitization, per-user rate limiting.
    """
    import uuid

    name = Path(file.filename or "upload").name
    name = re.sub(r"[^\w\-.]", "_", name)[:200]
    ext = Path(name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{ext}' not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    hasher = hashlib.sha256()
    total = 0
    await file.seek(0)
    while chunk := await file.read(CHUNK):
        total += len(chunk)
        hasher.update(chunk)
        if total > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max {MAX_BYTES // 1024 // 1024}MB for hackathon demo.",
            )
    await file.seek(0)

    return ValidationResult(
        original_filename=name,
        safe_filename=f"{uuid.uuid4()}{ext}",
        extension=ext,
        size_bytes=total,
        sha256=hasher.hexdigest(),
    )


def scan_for_injection(df: pd.DataFrame) -> None:
    """
    Lightweight CSV formula-injection guard.
    """
    if df is None or df.empty:
        return
    for col in df.columns:
        for value in df[col].dropna().astype(str):
            stripped = value.lstrip()
            if stripped.startswith(("=", "+", "@")):
                raise HTTPException(
                    status_code=400,
                    detail="Potential formula-injection content detected in uploaded dataset.",
                )


def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prefix potentially dangerous formula values with tab.
    """
    if df is None or df.empty:
        return df

    safe_df = df.copy()

    def _sanitize(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.lstrip()
        if stripped.startswith(("=", "+", "@")) and not value.startswith("\t"):
            return f"\t{value}"
        return value

    for col in safe_df.columns:
        safe_df[col] = safe_df[col].map(_sanitize)

    return safe_df
