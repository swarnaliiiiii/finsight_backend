"""RBI India macro data: scrapes the public RBI homepage statistics block since
RBI's DBIE API requires registration. Returns repo rate, inflation, FX reserves.
"""
from __future__ import annotations

import re
from datetime import date

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.sources.base import MacroPoint, MacroSource

_RBI_URL = "https://www.rbi.org.in/"


class RBISource(MacroSource):
    name = "rbi"
    countries = {"IN"}

    async def get_indicators(self, country: str) -> list[MacroPoint]:
        if country != "IN":
            return []
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS,
                                     headers={"User-Agent": settings.USER_AGENT}) as client:
            try:
                r = await client.get(_RBI_URL)
                r.raise_for_status()
                html = r.text
            except Exception:
                return []

        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)
        points: list[MacroPoint] = []
        today = date.today()

        patterns: list[tuple[str, str, str, str]] = [
            (r"Policy Repo Rate\s*:?\s*([\d.]+)", "RBI Repo Rate", "%", "IN"),
            (r"Reverse Repo Rate\s*:?\s*([\d.]+)", "RBI Reverse Repo Rate", "%", "IN"),
            (r"Bank Rate\s*:?\s*([\d.]+)", "RBI Bank Rate", "%", "IN"),
            (r"CRR\s*:?\s*([\d.]+)", "Cash Reserve Ratio", "%", "IN"),
            (r"SLR\s*:?\s*([\d.]+)", "Statutory Liquidity Ratio", "%", "IN"),
            (r"Inflation Rate.*?([\d.]+)", "India CPI Inflation", "%", "IN"),
        ]
        for pattern, display, unit, country_code in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            try:
                value = float(m.group(1))
                points.append(MacroPoint(indicator=display, country=country_code,
                                         value=value, unit=unit, as_of=today))
            except (ValueError, IndexError):
                continue
        return points
