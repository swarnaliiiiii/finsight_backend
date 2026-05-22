"""yfinance: free, no key, global coverage. Default price source for US/UK and
fallback for IN. yfinance is sync — we run it in a threadpool to keep FastAPI async.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import yfinance as yf

from app.sources.base import PricePoint, PriceQuote, PriceSource


class YFinanceSource(PriceSource):
    name = "yfinance"
    countries = {"US", "UK", "IN", "GLOBAL"}

    async def get_quote(self, ticker: str) -> PriceQuote | None:
        return await asyncio.to_thread(self._get_quote_sync, ticker)

    def _get_quote_sync(self, ticker: str) -> PriceQuote | None:
        try:
            t = yf.Ticker(ticker)
            info: dict[str, Any] = t.fast_info if hasattr(t, "fast_info") else {}
            price = float(info.get("last_price") or info.get("lastPrice") or 0)
            prev = float(info.get("previous_close") or info.get("previousClose") or 0)
            if not price:
                return None
            change = price - prev if prev else 0.0
            change_pct = (change / prev * 100) if prev else 0.0
            currency = info.get("currency") or "USD"
            return PriceQuote(
                ticker=ticker,
                price=price,
                change=change,
                change_percent=change_pct,
                currency=currency,
                as_of=datetime.utcnow(),
                name=getattr(t, "info", {}).get("shortName") if hasattr(t, "info") else None,
            )
        except Exception:
            return None

    async def get_history(self, ticker: str, *, period: str = "1mo") -> list[PricePoint]:
        return await asyncio.to_thread(self._get_history_sync, ticker, period)

    def _get_history_sync(self, ticker: str, period: str) -> list[PricePoint]:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=period)
            currency = getattr(t.fast_info, "currency", "USD") if hasattr(t, "fast_info") else "USD"
            out: list[PricePoint] = []
            for idx, row in df.iterrows():
                out.append(PricePoint(
                    ticker=ticker,
                    timestamp=idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else datetime.utcnow(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    currency=currency or "USD",
                ))
            return out
        except Exception:
            return []
