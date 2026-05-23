"""World Bank: cross-country macro indicators. No key, free, generous limits."""
from __future__ import annotations

import asyncio
from datetime import date

from app.layers.market_data.base import MacroPoint, MacroSource

_COUNTRY_ISO3 = {"IN": "IND", "US": "USA", "UK": "GBR"}
_INDICATORS: list[tuple[str, str, str]] = [
    ("NY.GDP.MKTP.KD.ZG", "Real GDP Growth", "%"),
    ("FP.CPI.TOTL.ZG", "CPI Inflation", "%"),
    ("SL.UEM.TOTL.ZS", "Unemployment Rate", "%"),
    ("FR.INR.RINR", "Real Interest Rate", "%"),
]


class WorldBankSource(MacroSource):
    name = "world_bank"
    countries = {"IN", "US", "UK", "GLOBAL"}

    async def get_indicators(self, country: str) -> list[MacroPoint]:
        iso3 = _COUNTRY_ISO3.get(country)
        if not iso3:
            return []
        return await asyncio.to_thread(self._fetch_sync, country, iso3)

    def _fetch_sync(self, country: str, iso3: str) -> list[MacroPoint]:
        try:
            import wbdata  # type: ignore
        except ImportError:
            return []
        points: list[MacroPoint] = []
        for code, display, unit in _INDICATORS:
            try:
                data = wbdata.get_data(code, country=iso3)
                if not data:
                    continue
                latest = next((d for d in data if d.get("value") is not None), None)
                if not latest:
                    continue
                year = int(latest["date"])
                points.append(MacroPoint(
                    indicator=display,
                    country=country,
                    value=float(latest["value"]),
                    unit=unit,
                    as_of=date(year, 12, 31),
                ))
            except Exception:
                continue
        return points
