"""FRED (St. Louis Fed): US macroeconomic data. fredapi is sync — threadpool wrapped."""
from __future__ import annotations

import asyncio
from datetime import date

from app.config import settings
from app.layers.market_data.base import MacroPoint, MacroSource

_US_INDICATORS: dict[str, tuple[str, str, str]] = {
    # series_id -> (display_name, unit, fred_series)
    "fed_funds_rate": ("Federal Funds Rate", "%", "FEDFUNDS"),
    "cpi": ("US CPI YoY", "%", "CPIAUCSL"),
    "unemployment": ("US Unemployment Rate", "%", "UNRATE"),
    "10y_treasury": ("10-Year Treasury Yield", "%", "DGS10"),
    "gdp": ("US Real GDP", "B USD", "GDPC1"),
}


class FREDSource(MacroSource):
    name = "fred"
    countries = {"US", "GLOBAL"}

    async def get_indicators(self, country: str) -> list[MacroPoint]:
        if not settings.FRED_API_KEY or country not in self.countries:
            return []
        return await asyncio.to_thread(self._fetch_sync, country)

    def _fetch_sync(self, country: str) -> list[MacroPoint]:
        try:
            from fredapi import Fred  # type: ignore
        except ImportError:
            return []
        try:
            fred = Fred(api_key=settings.FRED_API_KEY)
        except Exception:
            return []

        points: list[MacroPoint] = []
        for indicator, (display, unit, series_id) in _US_INDICATORS.items():
            try:
                series = fred.get_series(series_id)
                if series is None or series.empty:
                    continue
                latest = series.dropna().iloc[-1]
                latest_date = series.dropna().index[-1].date()
                points.append(MacroPoint(
                    indicator=display,
                    country="US",
                    value=float(latest),
                    unit=unit,
                    as_of=latest_date,
                ))
            except Exception:
                continue
        return points
