"""AMFI bulk NAV source.

AMFI publishes the full Indian mutual-fund universe once daily as a pipe-
delimited text file at https://www.amfiindia.com/spages/NAVAll.txt. This
source fetches it, caches the parse for 4h, and serves search + lookup
against the whole list — useful for social-proof rankings (every fund, not
just the ones a single client API returns).

Format (after a header line per AMC):
  Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

AMC blocks are introduced by lines like "Open Ended Schemes(Equity Scheme - ...)"
followed by an "AMC Name" line. We parse loosely and skip everything that
doesn't have 6 fields with a numeric NAV.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime

import httpx

from app.config import settings
from app.layers.market_data.base import FundInfo, FundSource

_AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
_CACHE_TTL_SECONDS = 4 * 60 * 60  # 4 hours


class AMFISource(FundSource):
    name = "amfi"
    countries = {"IN"}

    def __init__(self) -> None:
        self._cache: list[tuple[FundInfo, str | None]] = []  # (info, category)
        self._cache_ts: float = 0.0
        self._lock = asyncio.Lock()

    # --- public API -------------------------------------------------------

    async def search(self, query: str) -> list[FundInfo]:
        rows = await self._ensure_cache()
        if not query:
            return [r for r, _ in rows[:50]]
        q = query.lower()
        tokens = [t for t in q.split() if len(t) > 2]
        scored: list[tuple[int, FundInfo]] = []
        for info, _cat in rows:
            name_l = info.scheme_name.lower()
            hits = sum(1 for t in tokens if t in name_l)
            if hits:
                scored.append((hits, info))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [info for _, info in scored[:50]]

    async def get_nav(self, scheme_code: str) -> FundInfo | None:
        rows = await self._ensure_cache()
        for info, _cat in rows:
            if info.scheme_code == scheme_code:
                return info
        return None

    async def by_category(self, category_hint: str,
                            limit: int = 20) -> list[FundInfo]:
        """Convenience for the recommender: return funds whose category text
        contains `category_hint` (e.g. 'large cap', 'flexi', 'gilt')."""
        rows = await self._ensure_cache()
        c = category_hint.lower()
        return [info for info, cat in rows
                  if cat and c in cat.lower()][:limit]

    # --- cache machinery --------------------------------------------------

    async def _ensure_cache(self) -> list[tuple[FundInfo, str | None]]:
        now = time.time()
        if self._cache and (now - self._cache_ts) < _CACHE_TTL_SECONDS:
            return self._cache
        async with self._lock:
            now = time.time()
            if self._cache and (now - self._cache_ts) < _CACHE_TTL_SECONDS:
                return self._cache
            parsed = await self._fetch_and_parse()
            if parsed:
                self._cache = parsed
                self._cache_ts = now
            return self._cache

    async def _fetch_and_parse(self) -> list[tuple[FundInfo, str | None]]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers={"User-Agent": settings.USER_AGENT},
            ) as client:
                r = await client.get(_AMFI_URL)
                r.raise_for_status()
                text = r.text
        except (httpx.HTTPError, ValueError):
            return []
        return _parse_navall(text)


# --- pure parser ----------------------------------------------------------

def _parse_navall(text: str) -> list[tuple[FundInfo, str | None]]:
    rows: list[tuple[FundInfo, str | None]] = []
    current_category: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Category header lines look like "Open Ended Schemes(Equity Scheme - Large Cap Fund)"
        if "Schemes(" in line or "Scheme(" in line:
            current_category = line
            continue
        if ";" not in line:
            continue
        parts = line.split(";")
        if len(parts) < 6:
            continue
        scheme_code = parts[0].strip()
        scheme_name = parts[3].strip()
        nav_text = parts[4].strip()
        date_text = parts[5].strip()
        if not scheme_code or not scheme_name or scheme_code.lower() == "scheme code":
            continue
        try:
            nav = float(nav_text)
        except ValueError:
            continue
        as_of = _parse_date(date_text)
        rows.append((FundInfo(
            scheme_code=scheme_code,
            scheme_name=scheme_name,
            nav=nav,
            as_of=as_of,
            category=current_category,
            fund_house=None,  # AMFI file doesn't repeat AMC per row
        ), current_category))
    return rows


def _parse_date(value: str) -> date:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return date.today()
