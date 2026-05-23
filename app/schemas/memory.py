"""Memory schemas: what flows between the memory layer and the orchestrator.

The ORM models live inside `app.layers.memory.models` (private to the layer).
These public types are what agents (via AgentInput.upstream) ever see.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.intent import Intent
from app.schemas.user import InstrumentType, RiskLevel


class MemoryProfile(BaseModel, frozen=True):
    """Persistent user profile. Fields mirror UserContext where they overlap
    so the orchestrator can hydrate UserContext from this."""
    user_id: str
    country: str = "IN"
    age: int | None = None
    risk_tolerance: RiskLevel | None = None
    goal: str | None = None
    income_bracket: str | None = None
    comprehension_level: str = "beginner"
    instrument_type: InstrumentType | None = None
    amount: float | None = None
    horizon_years: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MemorySessionTurn(BaseModel, frozen=True):
    """One past conversation turn."""
    session_id: str
    query: str
    intent: Intent
    created_at: datetime


class MemoryActivity(BaseModel, frozen=True):
    """One past user action — viewed a term, compared funds, ran a projection."""
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MemoryReadout(BaseModel, frozen=True):
    """Snapshot the orchestrator builds at the start of each request and
    stashes into AgentInput.upstream so agents can read it without I/O."""
    profile: MemoryProfile
    recent_turns: list[MemorySessionTurn] = Field(default_factory=list)
    recent_activity: list[MemoryActivity] = Field(default_factory=list)
