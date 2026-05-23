"""Tavily: agent-optimized web search. Used by Deep Dive agent for niche instrument queries.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.layers.market_data.base import NewsItem, NewsSource


class TavilySource(NewsSource):
    name = "tavily"
    countries = {"IN", "US", "UK", "GLOBAL"}
    BASE_URL = "https://api.tavily.com/search"

    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 10) -> list[NewsItem]:
        if not settings.TAVILY_API_KEY or not query:
            return []
        country_hint = {"IN": "India", "US": "USA", "UK": "UK"}.get(country, "")
        enriched_query = f"{query} {country_hint} finance" if country_hint else f"{query} finance"
        payload = {
            "api_key": settings.TAVILY_API_KEY,
            "query": enriched_query,
            "search_depth": "advanced",
            "include_answer": False,
            "max_results": min(limit, 10),
            "topic": "news",
        }
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.post(self.BASE_URL, json=payload)
                r.raise_for_status()
                results = r.json().get("results", [])
            except Exception:
                return []

        items: list[NewsItem] = []
        for res in results[:limit]:
            published = datetime.utcnow()
            if res.get("published_date"):
                try:
                    published = datetime.fromisoformat(res["published_date"].replace("Z", "+00:00"))
                except Exception:
                    pass
            items.append(NewsItem(
                title=res.get("title", ""),
                url=res.get("url", ""),
                source="tavily",
                published_at=published,
                summary=res.get("content"),
                country=country,
            ))
        return items
