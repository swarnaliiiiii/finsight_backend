"""Current Scenario: the cached snapshot of the world the orchestrator injects
into instrument-related queries.

Produced by the Scenario layer's background refresher (lifespan asyncio task).
Consumed by agents as a read-only `AgentInput` field — agents never call the
scenario builder directly.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    WAR = "war"
    GEOPOLITICAL = "geopolitical"
    MONETARY_POLICY = "monetary_policy"
    FISCAL_POLICY = "fiscal_policy"
    REGULATORY = "regulatory"
    INFLATION_SHOCK = "inflation_shock"
    MARKET_CRASH = "market_crash"
    PANDEMIC = "pandemic"
    ELECTION = "election"
    BUDGET = "budget"


class Event(BaseModel, frozen=True):
    """A notable, ongoing real-world event affecting markets."""
    id: str
    type: EventType
    headline: str
    summary: str
    started_at: datetime | None = None
    sources: list[str] = Field(default_factory=list)


class MarketRegime(BaseModel, frozen=True):
    """Coarse-grained read of the current market state."""
    trend: str  # "bull" | "bear" | "sideways"
    volatility_band: str  # "low" | "normal" | "elevated" | "high"
    notes: str | None = None


class PolicyState(BaseModel, frozen=True):
    """Current rate-setting authority's stance."""
    authority: str  # "RBI" | "Federal Reserve" | "Bank of England"
    policy_rate: float | None = None
    policy_rate_unit: str = "percent"
    last_move: str | None = None  # "hike 25bp on 2026-04-05"
    next_meeting: datetime | None = None


class CurrentScenario(BaseModel, frozen=True):
    """The full snapshot. Refreshed every 4h by the Scenario layer."""
    refreshed_at: datetime
    country: str
    active_events: list[Event] = Field(default_factory=list)
    market_regime: MarketRegime | None = None
    policy_state: PolicyState | None = None
    instrument_tilts: dict[str, str] = Field(default_factory=dict)
    notable_headlines: list[str] = Field(default_factory=list)
