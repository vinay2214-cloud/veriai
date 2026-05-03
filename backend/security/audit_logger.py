"""Append-only chained audit logger (JSONL + SHA256 hash chain)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class ChainedAuditLogger:
    def __init__(self, log_path: str = "/data/datasets/audit.log.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha256_hex(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _last_entry_hash(self) -> str:
        if not self.log_path.exists():
            return "0" * 64

        last_hash = "0" * 64
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                parsed = json.loads(line)
                last_hash = parsed.get("entry_hash", last_hash)
        return last_hash

    def append(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        prev_entry_hash = self._last_entry_hash()
        entry_body = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "payload": payload,
        }
        canonical_json = json.dumps(entry_body, sort_keys=True, separators=(",", ":"))
        entry_hash = self._sha256_hex((prev_entry_hash + canonical_json).encode("utf-8"))

        full_entry = {
            **entry_body,
            "prev_entry_hash": prev_entry_hash,
            "entry_hash": entry_hash,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(full_entry, separators=(",", ":")) + "\n")
        return full_entry

    def verify(self) -> Dict[str, Any]:
        """Verify hash-chain integrity for every JSONL record."""
        if not self.log_path.exists():
            return {"valid": True, "entries_checked": 0, "message": "No log file found."}

        prev_hash = "0" * 64
        entries_checked = 0
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                stored_prev = entry.get("prev_entry_hash", "")
                stored_hash = entry.get("entry_hash", "")
                entry_body = {
                    "timestamp": entry.get("timestamp"),
                    "action": entry.get("action"),
                    "payload": entry.get("payload"),
                }
                canonical_json = json.dumps(entry_body, sort_keys=True, separators=(",", ":"))
                expected_hash = self._sha256_hex((prev_hash + canonical_json).encode("utf-8"))

                if stored_prev != prev_hash:
                    return {
                        "valid": False,
                        "entries_checked": entries_checked,
                        "error": f"Broken chain at line {line_no}: prev hash mismatch.",
                    }
                if stored_hash != expected_hash:
                    return {
                        "valid": False,
                        "entries_checked": entries_checked,
                        "error": f"Tamper detected at line {line_no}: entry hash mismatch.",
                    }

                prev_hash = stored_hash
                entries_checked += 1

        return {"valid": True, "entries_checked": entries_checked}

