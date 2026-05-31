"""SERP API (serpapi.com) news fallback.

Used when the primary news sources (Marketaux / Finnhub / NewsAPI) return
empty or error. SERP queries Google News and returns structured snippets.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.layers.market_data.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class SerpNewsSource(NewsSource):
    """Google-News-via-SERP-API. Fallback for the primary news providers."""

    name = "serp_news"

    async def fetch_news(self, *, query: str | None = None,
                          country: str = "IN", limit: int = 20
                          ) -> list[NewsItem]:
        if not settings.SERP_API_KEY:
            return []
        q = (query or self._default_query(country))
        gl = {"IN": "in", "US": "us", "UK": "uk"}.get(country, "us")
        params = {
            "engine": "google_news",
            "q": q,
            "gl": gl,
            "hl": "en",
            "api_key": settings.SERP_API_KEY,
        }
        try:
            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                r = await client.get("https://serpapi.com/search.json",
                                       params=params)
                r.raise_for_status()
                data = r.json()
        except Exception:
            logger.exception("SERP news fetch failed")
            return []
        items: list[NewsItem] = []
        for entry in (data.get("news_results") or [])[:limit]:
            # entries can be flat or grouped {stories: [...]}
            if "stories" in entry and isinstance(entry["stories"], list):
                for s in entry["stories"][:3]:
                    items.append(self._to_item(s))
            else:
                items.append(self._to_item(entry))
        # de-dupe by URL
        seen: set[str] = set()
        unique: list[NewsItem] = []
        for it in items:
            if it.url and it.url not in seen:
                seen.add(it.url)
                unique.append(it)
        return unique[:limit]

    def _default_query(self, country: str) -> str:
        return {
            "IN": "India stock market mutual funds investing today",
            "US": "US stock market investing today",
            "UK": "UK stock market FTSE investing today",
        }.get(country, "stock market investing today")

    def _to_item(self, entry: dict) -> NewsItem:
        published_at = self._parse_date(entry.get("date"))
        return NewsItem(
            source=entry.get("source", {}).get("name") if isinstance(
                entry.get("source"), dict) else (entry.get("source") or "google-news"),
            title=entry.get("title") or "",
            url=entry.get("link") or "",
            summary=entry.get("snippet") or entry.get("excerpt") or "",
            published_at=published_at,
            tickers=[],
            sentiment_score=None,
            sentiment_label=None,
        )

    def _parse_date(self, raw: str | None) -> datetime:
        if not raw:
            return datetime.now(timezone.utc)
        # SERP returns ISO datetimes for fresh news and "12 hours ago" for older.
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
