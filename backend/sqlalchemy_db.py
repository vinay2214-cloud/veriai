"""Async SQLAlchemy engine/session setup for PostgreSQL."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import DATABASE_URL, get_async_database_url
from .sqlalchemy_models import Base

_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def _build_engine() -> AsyncEngine:
    return create_async_engine(
        get_async_database_url(),
        echo=False,
        pool_pre_ping=True,
        future=True,
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_maker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for async DB sessions."""
    session_factory = get_session_maker()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


from sqlalchemy import text

async def init_sqlalchemy_models() -> None:
    """Create ORM tables on startup.
    Runs only when DATABASE_URL is configured.
    """
    if not DATABASE_URL:
        return
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Postgres trigger to prevent update on audits
        await conn.execute(text(
            "CREATE OR REPLACE FUNCTION prevent_audit_mod() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    RAISE EXCEPTION 'Audit log entries are immutable and cannot be updated.';\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;"
        ))
        await conn.execute(text("DROP TRIGGER IF EXISTS audits_prevent_mod ON audits;"))
        await conn.execute(text(
            "CREATE TRIGGER audits_prevent_mod\n"
            "BEFORE UPDATE ON audits\n"
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_mod();"
        ))

async def close_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None
