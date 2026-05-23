"""Internet consensus: what real beginners on Groww/Zerodha/Valueresearch prefer.

We scrape public pages with respectful rate limits (1 req/sec, cached 24h).
For US/UK we use Bogleheads/Reddit-style consensus from Tavily search since
US fund-comparison sites are gated.

This is intentionally best-effort — if a site changes its HTML we degrade
gracefully to empty results. The Advisor Agent will note when consensus data
is unavailable.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup
from cachetools import TTLCache

from app.config import settings
from app.schemas import InstrumentCandidate, InstrumentType

_consensus_cache: TTLCache = TTLCache(maxsize=200, ttl=24 * 60 * 60)


class ConsensusFetcher:
    """Per-country consensus aggregator."""

    async def fetch(self, *, instrument_type: InstrumentType, country: str,
                    category: str | None = None) -> list[InstrumentCandidate]:
        key = f"{country}:{instrument_type.value}:{category or 'all'}"
        if key in _consensus_cache:
            return _consensus_cache[key]
        if country == "IN":
            results = await self._fetch_india(instrument_type, category)
        elif country == "US":
            results = await self._fetch_us(instrument_type, category)
        elif country == "UK":
            results = await self._fetch_uk(instrument_type, category)
        else:
            results = []
        _consensus_cache[key] = results
        return results

    # --- India ----------------------------------------------------------------

    async def _fetch_india(self, instrument: InstrumentType,
                            category: str | None) -> list[InstrumentCandidate]:
        if instrument in (InstrumentType.SIP, InstrumentType.MUTUAL_FUND):
            results = await asyncio.gather(
                self._groww_top_funds(category),
                self._valueresearch_top_funds(category),
                return_exceptions=True,
            )
            merged: list[InstrumentCandidate] = []
            for r in results:
                if isinstance(r, list):
                    merged.extend(r)
            return self._dedupe(merged)
        if instrument == InstrumentType.STOCK:
            return await self._moneycontrol_top_stocks(category)
        if instrument == InstrumentType.ETF:
            return await self._groww_top_etfs()
        if instrument in (InstrumentType.BOND, InstrumentType.NCD, InstrumentType.FD):
            return await self._bondbazaar_or_fallback(instrument)
        return []

    async def _groww_top_funds(self, category: str | None) -> list[InstrumentCandidate]:
        url = "https://groww.in/mutual-funds/category/best-equity-mutual-funds"
        if category and "debt" in category.lower():
            url = "https://groww.in/mutual-funds/category/best-debt-mutual-funds"
        return await self._scrape_funds_listing(url, source_name="groww")

    async def _valueresearch_top_funds(self, category: str | None) -> list[InstrumentCandidate]:
        url = "https://www.valueresearchonline.com/funds/fund-selector/"
        return await self._scrape_funds_listing(url, source_name="valueresearch")

    async def _moneycontrol_top_stocks(self, category: str | None) -> list[InstrumentCandidate]:
        url = "https://www.moneycontrol.com/stocks/marketstats/nifty500-stocks/"
        candidates: list[InstrumentCandidate] = []
        html = await self._get(url)
        if not html:
            return candidates
        soup = BeautifulSoup(html, "lxml")
        for idx, row in enumerate(soup.select("table tbody tr")[:10]):
            cells = [c.get_text(strip=True) for c in row.select("td")]
            if len(cells) < 2:
                continue
            name = cells[0]
            link = row.select_one("a")
            candidates.append(InstrumentCandidate(
                id=f"moneycontrol:{name}",
                name=name,
                instrument_type=InstrumentType.STOCK,
                provider="NSE/BSE",
                consensus_rank=idx + 1,
                consensus_sources=["moneycontrol"],
                detail_url=link.get("href") if link else None,
                currency="INR",
            ))
        return candidates

    async def _groww_top_etfs(self) -> list[InstrumentCandidate]:
        return await self._scrape_funds_listing(
            "https://groww.in/etfs/best-etfs", source_name="groww", instrument_type=InstrumentType.ETF)

    async def _bondbazaar_or_fallback(self, instrument: InstrumentType) -> list[InstrumentCandidate]:
        return []

    async def _scrape_funds_listing(self, url: str, *, source_name: str,
                                      instrument_type: InstrumentType = InstrumentType.MUTUAL_FUND
                                      ) -> list[InstrumentCandidate]:
        html = await self._get(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        candidates: list[InstrumentCandidate] = []
        # Groww fund-card pattern: /mutual-funds/{slug}-direct-growth or
        # -direct-plan-growth. Excludes /category/, /filter, /amc, /debt-funds, etc.
        exclude_segments = {"category", "filter", "amc", "debt-funds", "equity-funds",
                            "elss", "tax-saving", "hybrid-funds", "what-is", "calculator",
                            "compare", "screener", "learn", "blog", "best-"}
        keep_suffixes = ("-direct-growth", "-direct-plan-growth", "-growth",
                         "-direct-plan", "-direct")

        for link in soup.select("a[href*='/mutual-funds/'], a[href*='/etfs/']"):
            href = link.get("href") or ""
            name = link.get_text(strip=True)
            if not name or len(name) < 6:
                continue

            path = href.split("?")[0].rstrip("/")
            slug = path.rsplit("/", 1)[-1] if "/" in path else path
            if any(seg in path for seg in exclude_segments):
                continue
            if not (slug.endswith(keep_suffixes) or instrument_type == InstrumentType.ETF):
                continue
            if any(w in name.lower() for w in ["learn", "calculator", "compare",
                                                 "blog", "screener", "view all"]):
                continue
            candidates.append(InstrumentCandidate(
                id=f"{source_name}:{slug}",
                name=name,
                instrument_type=instrument_type,
                provider=source_name,
                consensus_rank=len(candidates) + 1,
                consensus_sources=[source_name],
                detail_url=self._absolutize(url, href),
                currency="INR",
            ))
            if len(candidates) >= 10:
                break
        return candidates

    # --- US / UK --------------------------------------------------------------

    async def _fetch_us(self, instrument: InstrumentType,
                         category: str | None) -> list[InstrumentCandidate]:
        return await self._tavily_consensus(instrument, country="US")

    async def _fetch_uk(self, instrument: InstrumentType,
                         category: str | None) -> list[InstrumentCandidate]:
        return await self._tavily_consensus(instrument, country="UK")

    async def _tavily_consensus(self, instrument: InstrumentType,
                                  country: str) -> list[InstrumentCandidate]:
        if not settings.TAVILY_API_KEY:
            return []
        type_label = {
            InstrumentType.SIP: "index fund for beginners",
            InstrumentType.MUTUAL_FUND: "mutual fund",
            InstrumentType.STOCK: "stock for beginners",
            InstrumentType.ETF: "ETF",
            InstrumentType.BOND: "bond fund",
            InstrumentType.NCD: "corporate bond",
            InstrumentType.FD: "savings or CD",
        }[instrument]
        country_label = {"US": "USA", "UK": "UK"}.get(country, country)
        query = f"best {type_label} {country_label} for beginners 2026"
        payload = {
            "api_key": settings.TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 8,
            "topic": "general",
        }
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            try:
                r = await client.post("https://api.tavily.com/search", json=payload)
                r.raise_for_status()
                results = r.json().get("results", [])
            except Exception:
                return []

        currency = "USD" if country == "US" else "GBP" if country == "UK" else "USD"
        candidates: list[InstrumentCandidate] = []
        for idx, res in enumerate(results[:8]):
            candidates.append(InstrumentCandidate(
                id=f"tavily:{res.get('url','')}",
                name=res.get("title", "")[:100],
                instrument_type=instrument,
                consensus_rank=idx + 1,
                consensus_sources=["tavily-web"],
                review_summary=res.get("content"),
                detail_url=res.get("url"),
                currency=currency,
            ))
        return candidates

    # --- helpers --------------------------------------------------------------

    async def _get(self, url: str) -> str | None:
        await asyncio.sleep(1.0)
        try:
            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers={"User-Agent": settings.USER_AGENT},
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return r.text
        except Exception:
            return None
        return None

    @staticmethod
    def _absolutize(base: str, href: str | None) -> str | None:
        if not href:
            return None
        if href.startswith("http"):
            return href
        from urllib.parse import urljoin
        return urljoin(base, href)

    @staticmethod
    def _dedupe(items: list[InstrumentCandidate]) -> list[InstrumentCandidate]:
        seen: set[str] = set()
        out: list[InstrumentCandidate] = []
        for it in items:
            key = it.name.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out


consensus_fetcher = ConsensusFetcher()
