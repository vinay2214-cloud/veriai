"""Lazy retention cleanup for Render free-tier environments (no scheduler)."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

DATASETS_ROOT = Path(os.getenv("DATASETS_DIR", "/tmp/datasets"))
LAST_CLEANUP_FILE = DATASETS_ROOT / ".last_cleanup"
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _secure_overwrite(path: Path) -> None:
    """DoD 5220.22-M style overwrite: zeros, ones, random, then unlink."""
    if not path.exists() or not path.is_file():
        return

    size = path.stat().st_size
    if size < 0:
        size = 0

    with path.open("r+b", buffering=0) as handle:
        handle.seek(0)
        handle.write(b"\x00" * size)
        handle.flush()
        os.fsync(handle.fileno())

        handle.seek(0)
        handle.write(b"\xFF" * size)
        handle.flush()
        os.fsync(handle.fileno())

        handle.seek(0)
        handle.write(os.urandom(size))
        handle.flush()
        os.fsync(handle.fileno())

    path.unlink(missing_ok=True)


def _delete_dataset_dir(dataset_dir: Path) -> None:
    for child in dataset_dir.rglob("*"):
        if child.is_file():
            _secure_overwrite(child)
    # remove empty dirs deepest-first
    for child in sorted(dataset_dir.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()
    if dataset_dir.exists():
        dataset_dir.rmdir()


def _should_cleanup(now_epoch: float) -> bool:
    if not LAST_CLEANUP_FILE.exists():
        return True
    try:
        last = float(LAST_CLEANUP_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return True
    return now_epoch > (last + CLEANUP_INTERVAL_SECONDS)


def _touch_cleanup_time(now_epoch: float) -> None:
    DATASETS_ROOT.mkdir(parents=True, exist_ok=True)
    LAST_CLEANUP_FILE.write_text(str(now_epoch), encoding="utf-8")


def lazy_cleanup() -> Dict[str, int]:
    """Run retention cleanup at most once per 24h, triggered by request traffic."""
    now_epoch = time.time()
    if not _should_cleanup(now_epoch):
        return {"checked": 0, "deleted": 0}

    DATASETS_ROOT.mkdir(parents=True, exist_ok=True)
    now_dt = datetime.now(timezone.utc)
    checked = 0
    deleted = 0

    for user_dir in DATASETS_ROOT.iterdir():
        if not user_dir.is_dir():
            continue
        for dataset_dir in user_dir.iterdir():
            if not dataset_dir.is_dir():
                continue
            meta_path = dataset_dir / "metadata.json"
            if not meta_path.exists():
                continue
            checked += 1

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            retention_until = _parse_ts(meta.get("retention_until"))
            if retention_until is None:
                continue
            if now_dt >= retention_until:
                _delete_dataset_dir(dataset_dir)
                deleted += 1

        # remove now-empty user dirs
        if user_dir.exists() and not any(user_dir.iterdir()):
            user_dir.rmdir()

    _touch_cleanup_time(now_epoch)
    return {"checked": checked, "deleted": deleted}

