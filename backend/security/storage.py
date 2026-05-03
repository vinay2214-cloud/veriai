"""Secure dataset storage/retrieval with validation, redaction, and encryption."""
from __future__ import annotations

import gc
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile

from .encryption import DatasetEncryptor
from .file_validator import sanitize_dataframe, scan_for_injection, validate_upload
from .redactor import redact_for_gcp

DATASETS_ROOT = Path("/data/datasets")


def _wipe_bytearray(buf: bytearray | None) -> None:
    if buf is None:
        return
    for i in range(len(buf)):
        buf[i] = 0


async def store_dataset(
    *,
    file: UploadFile,
    user_id: str,
    dataset_id: str | None = None,
    is_demo: bool = False,
) -> dict:
    """Validate -> sanitize -> redact -> encrypt -> persist securely."""
    dataset_id = dataset_id or str(uuid.uuid4())
    upload_meta = await validate_upload(file)
    await file.seek(0)

    raw_upload = bytearray(await file.read())
    if not raw_upload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    plaintext_csv = None
    plaintext_buf = None
    try:
        df = pd.read_csv(io.BytesIO(raw_upload))
        scan_for_injection(df)

        sanitized_df = sanitize_dataframe(df)
        redacted_df = redact_for_gcp(sanitized_df, is_demo=is_demo)

        plaintext_csv = redacted_df.to_csv(index=False).encode("utf-8")
        plaintext_buf = bytearray(plaintext_csv)

        timestamp = datetime.now(timezone.utc).isoformat()
        encryptor = DatasetEncryptor()
        enc = encryptor.encrypt(
            bytes(plaintext_buf),
            user_id=str(user_id),
            dataset_id=str(dataset_id),
            sha256=upload_meta["sha256"],
            timestamp=timestamp,
        )

        target_dir = DATASETS_ROOT / str(user_id) / str(dataset_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        enc_path = target_dir / "data.enc"
        enc_path.write_text(enc["ciphertext_b64"], encoding="utf-8")

        metadata = {
            "user_id": str(user_id),
            "dataset_id": str(dataset_id),
            "filename": upload_meta.get("filename"),
            "mime_type": upload_meta.get("mime_type"),
            "size_bytes": upload_meta.get("size_bytes"),
            "sha256": upload_meta.get("sha256"),
            "timestamp": timestamp,
            "salt_b64": enc["salt_b64"],
            "nonce_b64": enc["nonce_b64"],
            "is_demo": bool(is_demo),
            "format": "csv",
            "encryption": "AES-256-GCM+PBKDF2-HMAC-SHA256",
        }
        (target_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "status": "stored",
            "dataset_id": str(dataset_id),
            "path": str(target_dir),
            "sha256": upload_meta["sha256"],
        }
    finally:
        _wipe_bytearray(raw_upload)
        _wipe_bytearray(plaintext_buf)
        if plaintext_csv is not None:
            plaintext_csv = b""
        gc.collect()


def retrieve_dataset(*, user_id: str, dataset_id: str) -> pd.DataFrame:
    """Verify ownership -> decrypt -> parse -> wipe raw bytes -> return DataFrame."""
    target_dir = DATASETS_ROOT / str(user_id) / str(dataset_id)
    meta_path = target_dir / "metadata.json"
    enc_path = target_dir / "data.enc"

    if not meta_path.exists() or not enc_path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found.")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if str(metadata.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Forbidden: dataset ownership mismatch.")
    if str(metadata.get("dataset_id")) != str(dataset_id):
        raise HTTPException(status_code=400, detail="Dataset metadata mismatch.")

    cipher_text = enc_path.read_text(encoding="utf-8")
    plain_bytes = None
    plain_buf = None
    try:
        encryptor = DatasetEncryptor()
        plain_bytes = encryptor.decrypt(
            ciphertext_b64=cipher_text,
            salt_b64=metadata["salt_b64"],
            nonce_b64=metadata["nonce_b64"],
            user_id=str(user_id),
            dataset_id=str(dataset_id),
            sha256=str(metadata["sha256"]),
            timestamp=str(metadata["timestamp"]),
        )

        plain_buf = bytearray(plain_bytes)
        df = pd.read_csv(io.BytesIO(plain_buf))
        return df
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to decrypt dataset: {exc}")
    finally:
        plain_bytes = b""
        _wipe_bytearray(plain_buf)
        gc.collect()

