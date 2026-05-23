"""NSE India: live Indian equity prices via nsepython. Sync lib — wrapped in threadpool."""
from __future__ import annotations

import asyncio
from datetime import datetime

from app.sources.base import PricePoint, PriceQuote, PriceSource


class NSESource(PriceSource):
    name = "nse"
    countries = {"IN"}

    async def get_quote(self, ticker: str) -> PriceQuote | None:
        return await asyncio.to_thread(self._get_quote_sync, ticker)

    def _get_quote_sync(self, ticker: str) -> PriceQuote | None:
        try:
            from nsepython import nse_quote_ltp, nse_eq  # type: ignore
        except ImportError:
            return None
        try:
            symbol = ticker.upper().replace(".NS", "")
            data = nse_eq(symbol)
            price_info = data.get("priceInfo", {})
            price = float(price_info.get("lastPrice", 0))
            if not price:
                return None
            change = float(price_info.get("change", 0))
            change_pct = float(price_info.get("pChange", 0))
            return PriceQuote(
                ticker=symbol,
                price=price,
                change=change,
                change_percent=change_pct,
                currency="INR",
                as_of=datetime.utcnow(),
                name=data.get("info", {}).get("companyName"),
            )
        except Exception:
            return None

    async def get_history(self, ticker: str, *, period: str = "1mo") -> list[PricePoint]:
        # nsepython historical APIs are slow + flaky; defer to yfinance via .NS suffix for history
        return []
