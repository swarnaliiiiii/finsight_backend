"""NewsAPI.org: general news search. Free tier = 100 req/day, localhost only."""
from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.layers.market_data.base import NewsItem, NewsSource

_COUNTRY_DOMAINS = {
    "IN": "moneycontrol.com,economictimes.indiatimes.com,livemint.com,business-standard.com",
    "US": "wsj.com,bloomberg.com,cnbc.com,reuters.com,marketwatch.com",
    "UK": "ft.com,bbc.co.uk,reuters.com,theguardian.com",
}


class NewsAPISource(NewsSource):
    name = "newsapi"
    countries = {"IN", "US", "UK", "GLOBAL"}
    BASE_URL = "https://newsapi.org/v2/everything"

    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 20) -> list[NewsItem]:
        if not settings.NEWSAPI_KEY:
            return []
        params = {
            "q": query or "finance OR markets OR stocks",
            "sortBy": "publishedAt",
            "pageSize": min(limit, 100),
            "language": "en",
            "apiKey": settings.NEWSAPI_KEY,
        }
        if country in _COUNTRY_DOMAINS:
            params["domains"] = _COUNTRY_DOMAINS[country]

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
                source=f"newsapi:{a.get('source', {}).get('name', '')}",
                published_at=published,
                summary=a.get("description"),
                country=country,
            ))
        return items
