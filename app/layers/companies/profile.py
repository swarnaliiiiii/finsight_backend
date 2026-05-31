"""Company profile: 10-year price series + key fundamentals.

Reads yfinance directly (the same source other PriceSources use). Returns a
shape the frontend's company-detail page can render without further fetches.

The SERP fallback for the textual 'business summary' lives in a sibling
helper so it can be called independently when the user hits the detail page.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _yf():
    # Local import — yfinance pulls in pandas + dateutil, which is slow and
    # we don't want it loaded by every layer-import path.
    import yfinance as yf
    return yf


async def get_company_profile(ticker: str) -> dict[str, Any] | None:
    """Return {ticker, name, sector, summary, fundamentals, price_history_10y,
    latest_news[]}. Each section is best-effort — None values where data is
    missing, never throws."""
    yf = _yf()

    def _sync_load() -> dict[str, Any] | None:
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            # 10y daily
            hist = tk.history(period="10y", interval="1d", auto_adjust=True)
            points: list[dict] = []
            if hist is not None and not hist.empty:
                for ts, row in hist.iterrows():
                    points.append({
                        "t": ts.strftime("%Y-%m-%d"),
                        "close": float(row["Close"]),
                    })
            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "summary": info.get("longBusinessSummary"),
                "country": info.get("country"),
                "website": info.get("website"),
                "currency": info.get("currency"),
                "fundamentals": {
                    "market_cap": info.get("marketCap"),
                    "trailing_pe": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "dividend_yield": info.get("dividendYield"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "beta": info.get("beta"),
                    "profit_margins": info.get("profitMargins"),
                    "revenue_growth": info.get("revenueGrowth"),
                    "return_on_equity": info.get("returnOnEquity"),
                },
                "price_history_10y": points,
                "latest_price": (points[-1]["close"] if points else None),
            }
        except Exception:
            logger.exception("yfinance company profile failed for %s", ticker)
            return None

    base = await asyncio.to_thread(_sync_load)
    if base is None:
        return None
    base["latest_news"] = await _serp_company_news(base["name"], ticker)
    return base


async def _serp_company_news(name: str | None, ticker: str) -> list[dict]:
    """Best-effort recent news for a company via SERP. Empty list on any failure."""
    if not settings.SERP_API_KEY:
        return []
    query = (name or ticker) + " stock news"
    params = {
        "engine": "google_news",
        "q": query,
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
        logger.exception("SERP company news failed for %s", ticker)
        return []
    out: list[dict] = []
    raw = data.get("news_results") or []
    for entry in raw[:8]:
        # entries may be grouped {stories: [...]}
        if "stories" in entry and isinstance(entry["stories"], list):
            for s in entry["stories"][:2]:
                out.append({
                    "title": s.get("title"),
                    "url": s.get("link"),
                    "source": (s.get("source") or {}).get("name")
                                if isinstance(s.get("source"), dict)
                                else s.get("source"),
                    "date": s.get("date"),
                    "snippet": s.get("snippet"),
                })
        else:
            out.append({
                "title": entry.get("title"),
                "url": entry.get("link"),
                "source": (entry.get("source") or {}).get("name")
                            if isinstance(entry.get("source"), dict)
                            else entry.get("source"),
                "date": entry.get("date"),
                "snippet": entry.get("snippet"),
            })
    return out[:10]
