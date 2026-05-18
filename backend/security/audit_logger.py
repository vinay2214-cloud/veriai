"""
Audit logging for hackathon: simple JSON file append.
Production: tamper-evident chain with SHA-256 hashing per entry.
"""
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    action: str
    user_id: str
    dataset_id: str
    ip: str
    result: str
    sha256: Optional[str] = None
    detail: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditLogger:
    """Hackathon: logs to Python logger. Production: chained JSONL files."""

    async def log(self, event: AuditEvent) -> None:
        logger.info(
            "[AUDIT] action=%s user=%s dataset=%s result=%s",
            event.action,
            event.user_id,
            event.dataset_id,
            event.result,
        )


class ChainedAuditLogger:
    """
    Backward-compatible shim for existing review route usage.
    """

    def append(self, action: str, payload: dict) -> dict:
        logger.info("[AUDIT] action=%s payload=%s", action, payload)
        return {"action": action, "payload": payload}
