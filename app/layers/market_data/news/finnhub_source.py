"""Finnhub: company + general news with built-in sentiment for US tickers."""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from app.config import settings
from app.layers.market_data.base import NewsItem, NewsSource


class FinnhubSource(NewsSource):
    name = "finnhub"
    countries = {"US", "GLOBAL"}
    BASE_URL = "https://finnhub.io/api/v1"

    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 20) -> list[NewsItem]:
        if not settings.FINNHUB_API_KEY:
            return []
        params: dict = {"token": settings.FINNHUB_API_KEY}
        if query:
            params.update({"symbol": query.upper(),
                           "from": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
                           "to": datetime.utcnow().strftime("%Y-%m-%d")})
            url = f"{self.BASE_URL}/company-news"
        else:
            params["category"] = "general"
            url = f"{self.BASE_URL}/news"

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
            except Exception:
                return []

        items: list[NewsItem] = []
        for entry in data[:limit]:
            items.append(NewsItem(
                title=entry.get("headline", ""),
                url=entry.get("url", ""),
                source=f"finnhub:{entry.get('source', '')}",
                published_at=datetime.utcfromtimestamp(entry.get("datetime", 0)),
                summary=entry.get("summary"),
                tickers=[query.upper()] if query else [],
                country=country,
            ))
        return items
