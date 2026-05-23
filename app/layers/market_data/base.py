"""Unified data models and base interfaces for all sources.

Every source returns these models regardless of the underlying provider so the
agent can compose results without caring which API the data came from.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Sentiment = Literal["positive", "negative", "neutral"]


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)
    sentiment_label: Sentiment | None = None
    tickers: list[str] = Field(default_factory=list)
    country: str = "GLOBAL"
    raw: dict | None = None

    @field_validator("published_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        return v


class PricePoint(BaseModel):
    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    currency: str = "USD"


class PriceQuote(BaseModel):
    ticker: str
    price: float
    change: float
    change_percent: float
    currency: str
    as_of: datetime
    name: str | None = None


class MacroPoint(BaseModel):
    indicator: str
    country: str
    value: float
    unit: str | None = None
    as_of: date


class FundInfo(BaseModel):
    scheme_code: str
    scheme_name: str
    nav: float
    as_of: date
    category: str | None = None
    fund_house: str | None = None


# --- Base classes ---------------------------------------------------------------


class BaseSource(ABC):
    """Marker base class; concrete sources inherit from a typed subclass below."""
    name: str
    countries: set[str]


class NewsSource(BaseSource):
    @abstractmethod
    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 20) -> list[NewsItem]:
        ...


class PriceSource(BaseSource):
    @abstractmethod
    async def get_quote(self, ticker: str) -> PriceQuote | None:
        ...

    @abstractmethod
    async def get_history(self, ticker: str, *, period: str = "1mo") -> list[PricePoint]:
        ...


class MacroSource(BaseSource):
    @abstractmethod
    async def get_indicators(self, country: str) -> list[MacroPoint]:
        ...


class FundSource(BaseSource):
    @abstractmethod
    async def search(self, query: str) -> list[FundInfo]:
        ...

    @abstractmethod
    async def get_nav(self, scheme_code: str) -> FundInfo | None:
        ...
