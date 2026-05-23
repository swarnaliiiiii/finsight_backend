"""GNews: Google News aggregator. Free tier = 100/day."""
from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.layers.market_data.base import NewsItem, NewsSource

_COUNTRY_MAP = {"IN": "in", "US": "us", "UK": "gb"}


class GNewsSource(NewsSource):
    name = "gnews"
    countries = {"IN", "US", "UK", "GLOBAL"}
    BASE_URL = "https://gnews.io/api/v4/search"

    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 20) -> list[NewsItem]:
        if not settings.GNEWS_API_KEY:
            return []
        params = {
            "q": query or "finance markets stocks",
            "lang": "en",
            "max": min(limit, 100),
            "apikey": settings.GNEWS_API_KEY,
        }
        if country in _COUNTRY_MAP:
            params["country"] = _COUNTRY_MAP[country]

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()
                articles = r.json().get("articles", [])
            except Exception:
                return []

        items: list[NewsItem] = []
        for a in articles[:limit]:
            try:
                published = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
            except Exception:
                published = datetime.utcnow()
            items.append(NewsItem(
                title=a.get("title", ""),
                url=a.get("url", ""),
                source=f"gnews:{a.get('source', {}).get('name', '')}",
                published_at=published,
                summary=a.get("description"),
                country=country,
            ))
        return items
