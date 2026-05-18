"""
Simple dataset storage for hackathon (no encryption).
Production: AES-256-GCM per-file encryption, ownership isolation,
DoD 5220.22-M secure delete, per-user directory isolation.
"""
import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from fastapi import UploadFile, HTTPException

from .file_validator import validate_upload

DATASETS_ROOT = Path(os.environ.get("DATASETS_DIR", "data/datasets"))


async def store_dataset(user_id: str, file: UploadFile, request_ip: str = "unknown") -> dict:
    validation = await validate_upload(file)
    dataset_id = str(uuid.uuid4())
    target_dir = DATASETS_ROOT / user_id / dataset_id
    target_dir.mkdir(parents=True, exist_ok=True)

    await file.seek(0)
    raw = await file.read()

    data_path = target_dir / f"data{validation.extension}"
    data_path.write_bytes(raw)

    meta = {
        "dataset_id": dataset_id,
        "user_id": user_id,
        "original_filename": validation.original_filename,
        "size_bytes": validation.size_bytes,
        "sha256": validation.sha256,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    (target_dir / "metadata.json").write_text(json.dumps(meta))
    return meta


async def retrieve_dataset(user_id: str, dataset_id: str, request_ip: str = "unknown") -> pd.DataFrame:
    target_dir = DATASETS_ROOT / user_id / dataset_id
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Dataset not found.")

    for ext in [".csv", ".xlsx", ".xls", ".json"]:
        p = target_dir / f"data{ext}"
        if p.exists():
            if ext == ".csv":
                return pd.read_csv(p)
            if ext in (".xlsx", ".xls"):
                return pd.read_excel(p)
            return pd.read_json(p)
    raise HTTPException(status_code=404, detail="Dataset file missing.")
