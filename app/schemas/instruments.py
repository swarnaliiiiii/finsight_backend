"""Instrument domain schemas: candidates, recommendations, comparisons,
explanations.

These cross the layer <-> orchestrator <-> agent boundary, so they live in
schemas/. Layers produce them; the orchestrator routes them; agents may read
them as `AgentInput.upstream` payloads.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.schemas.user import InstrumentType, RiskLevel, UserContext


class InstrumentCandidate(BaseModel):
    """A single fund/stock/bond/etc. with the factors that beginners care about."""
    id: str
    name: str
    instrument_type: InstrumentType
    provider: str | None = None
    category: str | None = None

    # universal scoring factors (None if unknown)
    returns_1y: float | None = None
    returns_3y: float | None = None
    returns_5y: float | None = None
    expense_ratio: float | None = None
    aum_crore: float | None = None
    risk_level: RiskLevel | None = None
    min_investment: float | None = None

    # consensus signals
    consensus_rank: int | None = None
    consensus_sources: list[str] = Field(default_factory=list)
    review_summary: str | None = None

    # links the user can click in the web app
    detail_url: str | None = None
    currency: str = "INR"


class AffectingEntity(BaseModel):
    """One thing that affects an instrument's value/return."""
    name: str
    description: str
    direction: str
    data_source: str | None = None
    current_value: str | None = None
    impact_level: str = "moderate"


class Explanation(BaseModel):
    """Beginner-friendly explanation of an instrument type or term."""
    term: str
    plain_english: str
    why_it_matters: str
    affecting_entities: list[AffectingEntity]
    related_terms: list[str] = Field(default_factory=list)


_DISCLAIMER = (
    "This is educational information based on public data, not financial advice. "
    "Past performance does not guarantee future returns. Please consult a "
    "SEBI-registered investment advisor (or equivalent in your country) before investing."
)


class Recommendation(BaseModel):
    """Final output the Advisor flow returns to the web app."""
    user_context: UserContext
    candidates: list[InstrumentCandidate]
    top_pick_id: str | None = None
    reasoning: str
    explanation: Explanation | None = None
    consensus_summary: str | None = None
    factors_used: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = _DISCLAIMER


class Comparison(BaseModel):
    """Side-by-side breakdown of N candidates."""
    candidates: list[InstrumentCandidate]
    factors: list[str]
    winner_by_factor: dict[str, str]
    summary: str
    disclaimer: str = _DISCLAIMER
