"""Marketaux: finance-focused news with entity tagging and sentiment scores."""
from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.sources.base import NewsItem, NewsSource

_COUNTRY_MAP = {"IN": "in", "US": "us", "UK": "gb"}


class MarketauxSource(NewsSource):
    name = "marketaux"
    countries = {"IN", "US", "UK", "GLOBAL"}
    BASE_URL = "https://api.marketaux.com/v1/news/all"

    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 20) -> list[NewsItem]:
        if not settings.MARKETAUX_API_KEY:
            return []
        params = {
            "api_token": settings.MARKETAUX_API_KEY,
            "language": "en",
            "limit": min(limit, 50),
        }
        if query:
            params["search"] = query
        if country in _COUNTRY_MAP:
            params["countries"] = _COUNTRY_MAP[country]

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()
                articles = r.json().get("data", [])
            except Exception:
                return []

        items: list[NewsItem] = []
        for a in articles[:limit]:
            try:
                published = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
            except Exception:
                published = datetime.utcnow()
            entities = a.get("entities", [])
            sentiments = [e.get("sentiment_score") for e in entities if e.get("sentiment_score") is not None]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None
            label = None
            if avg_sentiment is not None:
                label = "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
            tickers = [e.get("symbol") for e in entities if e.get("symbol")]
            items.append(NewsItem(
                title=a.get("title", ""),
                url=a.get("url", ""),
                source=f"marketaux:{a.get('source', '')}",
                published_at=published,
                summary=a.get("description") or a.get("snippet"),
                sentiment_score=avg_sentiment,
                sentiment_label=label,  # type: ignore[arg-type]
                tickers=tickers,
                country=country,
            ))
        return items
