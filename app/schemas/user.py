"""User-facing enums and the UserContext profile.

UserContext is the orchestrator-owned snapshot of what we know about the user
for a given query. Agents read it; they never mutate it.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class InstrumentType(str, Enum):
    SIP = "sip"
    MUTUAL_FUND = "mutual_fund"
    STOCK = "stock"
    ETF = "etf"
    BOND = "bond"
    NCD = "ncd"
    FD = "fd"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class UserContext(BaseModel, frozen=True):
    """Frozen profile passed to agents. Memory layer (later) is the writer."""
    country: str = "IN"
    instrument_type: InstrumentType | None = None
    amount: float | None = None
    horizon_years: int | None = None
    risk_tolerance: RiskLevel | None = None
    goal: str | None = None
    age: int | None = None
    income_bracket: str | None = None
    comprehension_level: str = "beginner"
