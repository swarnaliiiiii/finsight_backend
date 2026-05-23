"""SQLAlchemy ORM models — private to the memory layer.

Columns use portable types so the schema works on both Postgres (where the
production app runs) and SQLite (where smoke tests run).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (BigInteger, DateTime, ForeignKey, Index, Integer,
                          Numeric, String, Text, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# SQLite's autoincrement only works on the literal `INTEGER PRIMARY KEY`
# type. Postgres can use BIGINT freely. Use the variant so both work.
_BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    country: Mapped[str] = mapped_column(String(8), nullable=False, default="IN")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_tolerance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    income_bracket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comprehension_level: Mapped[str] = mapped_column(
        String(32), nullable=False, default="beginner")
    instrument_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    horizon_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        onupdate=_utcnow, server_default=func.now())

    turns: Mapped[list["SessionTurn"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")
    activity: Mapped[list["ActivityEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class SessionTurn(Base):
    __tablename__ = "session_turns"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True,
                                       autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    envelope: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        server_default=func.now())

    user: Mapped[UserProfile] = relationship(back_populates="turns")

    __table_args__ = (
        Index("ix_session_turns_user_created",
                "user_id", "created_at"),
        Index("ix_session_turns_session_created",
                "session_id", "created_at"),
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True,
                                       autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        server_default=func.now())

    user: Mapped[UserProfile] = relationship(back_populates="activity")

    __table_args__ = (
        Index("ix_activity_events_user_created",
                "user_id", "created_at"),
    )
