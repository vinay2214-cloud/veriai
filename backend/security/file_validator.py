"""Upload validation and CSV injection protection utilities."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import HTTPException, UploadFile

try:
    import magic  # provided by python-magic-bin
except Exception:  # pragma: no cover
    magic = None

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
_CHUNK_SIZE = 1024 * 1024  # 1MB
_MIME_SNIFF_BYTES = 4096

ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "text/x-csv",
    "text/plain",
    "text/comma-separated-values",
    "application/vnd.ms-excel",
}

ALLOWED_EXTENSIONS = {".csv"}


def _is_dangerous_text(value: str) -> bool:
    if not value:
        return False
    text = value.lstrip()
    if text.startswith(("=", "+", "@", "|")):
        return True
    lowered = text.lower()
    return lowered.startswith("<script") or lowered.startswith("=cmd(")


async def validate_upload(file: UploadFile) -> Dict[str, Any]:
    """Stream-validate file size + SHA256 and verify MIME/extension."""
    if file is None:
        raise HTTPException(status_code=400, detail="No file provided.")

    digest = hashlib.sha256()
    size = 0
    sniff = bytearray()

    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break

        size += len(chunk)
        if size > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="File exceeds max allowed size (50MB).")

        digest.update(chunk)
        if len(sniff) < _MIME_SNIFF_BYTES:
            needed = _MIME_SNIFF_BYTES - len(sniff)
            sniff.extend(chunk[:needed])

    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if magic is None:
        raise HTTPException(status_code=503, detail="MIME detector unavailable on server.")

    detected_mime = magic.from_buffer(bytes(sniff), mime=True) if sniff else "application/octet-stream"
    extension = Path(file.filename or "").suffix.lower()
    if detected_mime not in ALLOWED_MIME_TYPES and extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: mime={detected_mime}, extension={extension or 'none'}",
        )

    await file.seek(0)
    return {
        "filename": file.filename,
        "size_bytes": size,
        "sha256": digest.hexdigest(),
        "mime_type": detected_mime,
    }


def scan_for_injection(df: pd.DataFrame) -> None:
    """Raise HTTP 400 if potentially dangerous formula/script cells are present."""
    if df is None or df.empty:
        return

    findings: List[Dict[str, Any]] = []
    for col_name in df.columns:
        series = df[col_name]
        for row_idx, value in series.items():
            if isinstance(value, str) and _is_dangerous_text(value):
                findings.append(
                    {
                        "row": int(row_idx),
                        "column": str(col_name),
                        "value_preview": value[:80],
                    }
                )
                if len(findings) >= 10:
                    break
        if len(findings) >= 10:
            break

    if findings:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Potential CSV/Excel injection detected in uploaded data.",
                "findings": findings,
            },
        )


def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Neutralize dangerous formula/script prefixes by prepending a tab."""
    if df is None or df.empty:
        return df

    safe_df = df.copy(deep=True)
    for col_name in safe_df.columns:
        def _sanitize(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            if value.startswith("\t"):
                return value
            if _is_dangerous_text(value):
                return f"\t{value}"
            return value

        safe_df[col_name] = safe_df[col_name].map(_sanitize)
    return safe_df
