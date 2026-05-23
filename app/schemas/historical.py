"""Historical-analytics schemas: curated eras, window-level performance,
end-to-end report passed from the historical layer to the historical agent.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Era(BaseModel, frozen=True):
    """A curated, named historical window.

    The `categories` list lets the lookup layer match free-form queries:
    ('crash', 'pandemic') matches both 'covid' and 'crash' queries.
    """
    id: str
    label: str
    start_date: date
    end_date: date
    countries: list[str] = Field(default_factory=list)  # ISO codes; empty = global
    categories: list[str] = Field(default_factory=list)
    summary: str = ""


class EraPerformance(BaseModel, frozen=True):
    """Deterministic stats for one instrument across one era window."""
    ticker: str
    era_id: str
    start_price: float | None
    end_price: float | None
    period_return_pct: float | None
    max_drawdown_pct: float | None
    annualized_volatility_pct: float | None
    points: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HistoricalReport(BaseModel, frozen=True):
    """The historical layer's full response: the era it matched, the
    representative ticker used, and the computed performance."""
    era: Era
    instrument_label: str  # human-friendly, e.g. "Gold ETF (proxy: GOLDBEES.NS)"
    ticker: str
    performance: EraPerformance | None
