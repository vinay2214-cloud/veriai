"""SQLAlchemy ORM models for Postgres-backed persistence."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    audits: Mapped[List["Audit"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    input: Mapped[str] = mapped_column(Text, nullable=False)
    bias_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    truth_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trust_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    corrected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_type: Mapped[str] = mapped_column(String(32), default="dataset", nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    column_mapping: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="audits")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
