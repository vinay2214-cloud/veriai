'''backend/database.py'''
"""Async SQLite helper for VeriAI.
Provides simple CRUD utilities and ensures tables are created on startup.
The design abstracts the DB so swapping to Firestore later is straightforward.
"""
import aiosqlite
import json
from pathlib import Path
from .config import (
    DB_PATH,
    LOG_LEVEL,
    MAX_AUDIT_RECORDS,
    MAX_FEEDBACK_RECORDS,
    MAX_KB_ARTICLES,
    MAX_REPORT_JSON_CHARS,
    MAX_REVIEW_RECORDS,
)
import logging

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema definitions (SQL)
# ---------------------------------------------------------------------------
SCHEMA = {
    "audits": """
        CREATE TABLE IF NOT EXISTS audits (
            id TEXT PRIMARY KEY,
            input TEXT NOT NULL,
            bias_score REAL,
            truth_score REAL,
            trust_score REAL,
            corrected TEXT,
            audit_type TEXT DEFAULT 'dataset',
            model_name TEXT,
            prompt TEXT,
            report_json TEXT,
            column_mapping TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "logs": """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT,
            issue TEXT,
            severity TEXT,
            resolved INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "feedback": """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT,
            correct INTEGER,
            bias_flag INTEGER,
            notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "knowledge_base": """
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            source TEXT
        );
    """,
    "review_queue": """
        CREATE TABLE IF NOT EXISTS review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            trust_score REAL,
            input_preview TEXT,
            status TEXT DEFAULT 'pending',
            reviewer_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        );
    """,
}

AUDIT_COLUMNS = {
    "audit_type": "TEXT DEFAULT 'dataset'",
    "model_name": "TEXT",
    "prompt": "TEXT",
    "report_json": "TEXT",
    "column_mapping": "TEXT",
}

async def init_db() -> None:
    """Create tables if they do not exist.
    Called from FastAPI startup event.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        for name, stmt in SCHEMA.items():
            await db.execute(stmt)
            logger.debug(f"Ensured table {name} exists")
        await db.commit()
    # Ignore already-existing column errors in a follow-up pass
    async with aiosqlite.connect(DB_PATH) as db:
        for col, col_type in AUDIT_COLUMNS.items():
            try:
                await db.execute(f"ALTER TABLE audits ADD COLUMN {col} {col_type};")
            except aiosqlite.OperationalError:
                pass
        await db.commit()

# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
async def execute(query: str, params: tuple = ()) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()

async def fetch_one(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row

async def fetch_all(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return rows


def _truncate(value, max_chars: int):
    if value is None:
        return value
    text = str(value)
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def _compact_report_json(report_json):
    """Keep persisted reports useful but bounded for Render storage."""
    if report_json is None:
        return None
    try:
        report = json.loads(json.dumps(report_json, default=str))
    except Exception:
        report = {"summary": _truncate(report_json, 1000)}

    if isinstance(report, dict):
        report["input_text"] = _truncate(report.get("input_text", ""), 500)
        report["corrections"] = _truncate(report.get("corrections", ""), 1200)

        truth = report.get("truth")
        if isinstance(truth, dict):
            citations = truth.get("citations") or []
            truth["citations"] = [
                {
                    **citation,
                    "snippet": _truncate(citation.get("snippet", ""), 220),
                    "source_text": _truncate(citation.get("source_text", ""), 220),
                }
                for citation in citations[:5]
                if isinstance(citation, dict)
            ]

            compact_claims = []
            for claim in (truth.get("claim_citations") or [])[:5]:
                if not isinstance(claim, dict):
                    continue
                item = dict(claim)
                item.pop("retrieved_context", None)
                item["source_text"] = _truncate(item.get("source_text", ""), 220)
                compact_claims.append(item)
            truth["claim_citations"] = compact_claims

        report["storage_policy"] = "compact_report_json_raw_uploads_not_stored"

    payload = json.dumps(report, separators=(",", ":"))
    if len(payload) > MAX_REPORT_JSON_CHARS:
        minimal = {
            "audit_id": report.get("audit_id") if isinstance(report, dict) else None,
            "audit_type": report.get("audit_type") if isinstance(report, dict) else None,
            "trust_score": report.get("trust_score") if isinstance(report, dict) else None,
            "bias": report.get("bias") if isinstance(report, dict) else None,
            "truth": report.get("truth") if isinstance(report, dict) else None,
            "cluster": report.get("cluster") if isinstance(report, dict) else None,
            "distribution": report.get("distribution") if isinstance(report, dict) else None,
            "reasoning_steps": report.get("reasoning_steps") if isinstance(report, dict) else None,
            "storage_policy": "minimal_report_json_size_cap_applied",
        }
        payload = json.dumps(minimal, separators=(",", ":"))
    return payload


async def prune_storage() -> None:
    """Bound demo SQLite growth for storage-limited Render deployments."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM audits WHERE id NOT IN (SELECT id FROM audits ORDER BY created_at DESC LIMIT ?)",
            (MAX_AUDIT_RECORDS,),
        )
        await db.execute(
            "DELETE FROM review_queue WHERE id NOT IN (SELECT id FROM review_queue ORDER BY id DESC LIMIT ?)",
            (MAX_REVIEW_RECORDS,),
        )
        await db.execute(
            "DELETE FROM feedback WHERE id NOT IN (SELECT id FROM feedback ORDER BY id DESC LIMIT ?)",
            (MAX_FEEDBACK_RECORDS,),
        )
        await db.execute(
            "DELETE FROM knowledge_base WHERE id NOT IN (SELECT id FROM knowledge_base ORDER BY id DESC LIMIT ?)",
            (MAX_KB_ARTICLES,),
        )
        await db.execute("PRAGMA optimize;")
        await db.commit()


# Convenience wrappers for audit table
async def insert_audit(audit_id: str, input_text: str, bias_score: float = None,
                       truth_score: float = None, trust_score: float = None,
                       corrected: str = None, audit_type: str = "dataset",
                       model_name: str = None, prompt: str = None, report_json=None,
                       column_mapping: str = None) -> None:
    report_payload = _compact_report_json(report_json)
    await execute(
        "INSERT OR REPLACE INTO audits (id, input, bias_score, truth_score, trust_score, corrected, audit_type, model_name, prompt, report_json, column_mapping) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (audit_id, _truncate(input_text, 500), bias_score, truth_score, trust_score, _truncate(corrected, 1200), audit_type, model_name, _truncate(prompt, 500), report_payload, column_mapping),
    )
    await prune_storage()

async def get_audit(audit_id: str):
    row = await fetch_one(
        "SELECT id, input, bias_score, truth_score, trust_score, corrected, audit_type, model_name, prompt, report_json, column_mapping, created_at FROM audits WHERE id = ?",
        (audit_id,),
    )
    return row

async def list_audits(limit: int = 20):
    rows = await fetch_all("SELECT id, input, trust_score, created_at, audit_type FROM audits ORDER BY created_at DESC LIMIT ?", (limit,))
    return rows

# Review queue helpers
async def insert_review(audit_id: str, trust_score: float, input_preview: str) -> None:
    await execute(
        "INSERT INTO review_queue (audit_id, trust_score, input_preview) VALUES (?, ?, ?)",
        (audit_id, trust_score, input_preview[:200]),
    )

async def get_pending_reviews(limit: int = 50):
    rows = await fetch_all(
        "SELECT id, audit_id, trust_score, input_preview, status, reviewer_notes, created_at, reviewed_at "
        "FROM review_queue ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return rows

async def update_review_status(audit_id: str, status: str, notes: str = "") -> None:
    await execute(
        "UPDATE review_queue SET status = ?, reviewer_notes = ?, reviewed_at = CURRENT_TIMESTAMP WHERE audit_id = ?",
        (status, notes, audit_id),
    )

async def get_review_stats():
    pending = await fetch_one("SELECT COUNT(*) FROM review_queue WHERE status = 'pending'")
    approved = await fetch_one("SELECT COUNT(*) FROM review_queue WHERE status = 'approved'")
    rejected = await fetch_one("SELECT COUNT(*) FROM review_queue WHERE status = 'rejected'")
    escalated = await fetch_one("SELECT COUNT(*) FROM review_queue WHERE status = 'escalated'")
    return {
        "pending": pending[0] if pending else 0,
        "approved": approved[0] if approved else 0,
        "rejected": rejected[0] if rejected else 0,
        "escalated": escalated[0] if escalated else 0,
    }


async def get_review_by_audit(audit_id: str):
    row = await fetch_one(
        "SELECT status, reviewer_notes, created_at, reviewed_at FROM review_queue WHERE audit_id = ? ORDER BY id DESC LIMIT 1",
        (audit_id,),
    )
    if not row:
        return None
    return {
        "status": row[0],
        "reviewer_notes": row[1] or "",
        "created_at": row[2],
        "reviewed_at": row[3],
    }
