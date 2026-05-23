"""Alpha Vantage: backup for prices. Free tier = 25 calls/day, use sparingly."""
from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.layers.market_data.base import PricePoint, PriceQuote, PriceSource


class AlphaVantageSource(PriceSource):
    name = "alpha_vantage"
    countries = {"US", "UK", "IN", "GLOBAL"}
    BASE_URL = "https://www.alphavantage.co/query"

    async def get_quote(self, ticker: str) -> PriceQuote | None:
        if not settings.ALPHA_VANTAGE_KEY:
            return None
        params = {"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": settings.ALPHA_VANTAGE_KEY}
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()
                data = r.json().get("Global Quote", {})
                price = float(data.get("05. price", 0) or 0)
                if not price:
                    return None
                change = float(data.get("09. change", 0) or 0)
                change_pct_str = (data.get("10. change percent", "0") or "0").rstrip("%")
                return PriceQuote(
                    ticker=ticker,
                    price=price,
                    change=change,
                    change_percent=float(change_pct_str),
                    currency="USD",
                    as_of=datetime.utcnow(),
                )
            except Exception:
                return None

    async def get_history(self, ticker: str, *, period: str = "1mo") -> list[PricePoint]:
        if not settings.ALPHA_VANTAGE_KEY:
            return []
        params = {"function": "TIME_SERIES_DAILY", "symbol": ticker, "apikey": settings.ALPHA_VANTAGE_KEY,
                  "outputsize": "compact"}
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()
                series = r.json().get("Time Series (Daily)", {})
                out: list[PricePoint] = []
                for date_str, row in list(series.items())[:30]:
                    out.append(PricePoint(
                        ticker=ticker,
                        timestamp=datetime.fromisoformat(date_str),
                        open=float(row["1. open"]),
                        high=float(row["2. high"]),
                        low=float(row["3. low"]),
                        close=float(row["4. close"]),
                        volume=int(row["5. volume"]),
                        currency="USD",
                    ))
                return out
            except Exception:
                return []
