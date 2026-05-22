"""RSS feeds: Indian financial publishers (Moneycontrol, ET) and other free feeds.
No API key. feedparser is sync — wrapped in threadpool.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from time import mktime

import feedparser

from app.sources.base import NewsItem, NewsSource

_FEEDS: dict[str, list[tuple[str, str]]] = {
    "IN": [
        ("moneycontrol_business", "https://www.moneycontrol.com/rss/business.xml"),
        ("moneycontrol_markets", "https://www.moneycontrol.com/rss/marketreports.xml"),
        ("economic_times_markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
        ("livemint_markets", "https://www.livemint.com/rss/markets"),
    ],
    "US": [
        ("cnbc_business", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
        ("yahoo_finance", "https://finance.yahoo.com/news/rssindex"),
    ],
    "UK": [
        ("bbc_business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("guardian_business", "https://www.theguardian.com/uk/business/rss"),
    ],
    "GLOBAL": [
        ("reuters_business", "https://feeds.reuters.com/reuters/businessNews"),
    ],
}


class _BaseRSSSource(NewsSource):
    feed_key: str = ""

    async def fetch_news(self, *, query: str | None = None, country: str = "GLOBAL",
                         limit: int = 20) -> list[NewsItem]:
        feeds = _FEEDS.get(country, []) + _FEEDS.get("GLOBAL", [])
        if self.feed_key:
            feeds = [f for f in feeds if f[0].startswith(self.feed_key)]
        return await asyncio.to_thread(self._parse_feeds, feeds, query, country, limit)

    def _parse_feeds(self, feeds: list[tuple[str, str]], query: str | None,
                     country: str, limit: int) -> list[NewsItem]:
        items: list[NewsItem] = []
        q_lower = query.lower() if query else None
        for source_name, url in feeds:
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries[:50]:
                    title = entry.get("title", "")
                    if q_lower and q_lower not in title.lower():
                        continue
                    published = datetime.utcnow()
                    if entry.get("published_parsed"):
                        published = datetime.fromtimestamp(mktime(entry.published_parsed))
                    items.append(NewsItem(
                        title=title,
                        url=entry.get("link", ""),
                        source=f"rss:{source_name}",
                        published_at=published,
                        summary=entry.get("summary"),
                        country=country,
                    ))
            except Exception:
                continue
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit]


class MoneycontrolRSSSource(_BaseRSSSource):
    name = "rss_moneycontrol"
    countries = {"IN"}
    feed_key = "moneycontrol"


class EconomicTimesRSSSource(_BaseRSSSource):
    name = "rss_economic_times"
    countries = {"IN"}
    feed_key = "economic_times"


class GenericRSSSource(_BaseRSSSource):
    """All feeds for the given country (used as a catch-all)."""
    name = "rss"
    countries = {"IN", "US", "UK", "GLOBAL"}
    feed_key = ""
