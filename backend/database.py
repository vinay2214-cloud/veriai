'''backend/database.py'''
"""Async SQLite helper for VeriAI.
Provides simple CRUD utilities and ensures tables are created on startup.
The design abstracts the DB so swapping to Firestore later is straightforward.
"""
import aiosqlite
import json
from pathlib import Path
from .config import DB_PATH, LOG_LEVEL
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

# Convenience wrappers for audit table
async def insert_audit(audit_id: str, input_text: str, bias_score: float = None,
                       truth_score: float = None, trust_score: float = None,
                       corrected: str = None, audit_type: str = "dataset",
                       model_name: str = None, prompt: str = None, report_json=None,
                       column_mapping: str = None) -> None:
    report_payload = json.dumps(report_json) if report_json is not None else None
    await execute(
        "INSERT OR REPLACE INTO audits (id, input, bias_score, truth_score, trust_score, corrected, audit_type, model_name, prompt, report_json, column_mapping) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (audit_id, input_text, bias_score, truth_score, trust_score, corrected, audit_type, model_name, prompt, report_payload, column_mapping),
    )

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
