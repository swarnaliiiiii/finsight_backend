"""Daily Brief response schemas + the per-layer Signal contract."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import InstrumentType


class BriefSeverity(str, Enum):
    INFO = "info"
    WATCH = "watch"
    IMPORTANT = "important"


class BriefSourceType(str, Enum):
    NEWS = "news"
    MACRO = "macro"
    INDEX = "index"
    SENTIMENT = "sentiment"


class Signal(BaseModel):
    """Candidate signal produced by the brief_signals layer and consumed by
    the brief agent. Schema-level so it can cross the layer<->agent boundary."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str
    raw_data: str
    source_type: BriefSourceType
    affected_instruments: list[InstrumentType] = Field(default_factory=list)
    severity: BriefSeverity = BriefSeverity.INFO
    source_links: list[str] = Field(default_factory=list)
    learn_more_terms: list[str] = Field(default_factory=list)
    importance_score: float = 0.5


class BriefItem(BaseModel):
    """A single action item in the Daily Brief."""
    title: str
    plain_english: str
    why_it_matters: str
    affected_instruments: list[InstrumentType] = Field(default_factory=list)
    severity: BriefSeverity = BriefSeverity.INFO
    source_type: BriefSourceType
    source_links: list[str] = Field(default_factory=list)
    learn_more_terms: list[str] = Field(default_factory=list)


class DailyBrief(BaseModel):
    """The full Daily Brief returned to the web app."""
    country: str
    market_summary: str
    items: list[BriefItem]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache_ttl_seconds: int = 4 * 60 * 60
    disclaimer: str = (
        "This is educational information based on public data, not financial advice. "
        "Markets move daily — don't make snap decisions on a single brief."
    )
