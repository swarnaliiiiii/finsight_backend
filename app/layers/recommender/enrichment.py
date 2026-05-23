"""Enrich consensus candidates with real data from our source layer.

After consensus.py gives us a list of names (e.g., "HDFC Top 100 Fund"), we
look up NAV, expense ratio, AUM, returns from mftool/yfinance/finnhub before
the scoring engine can rank them.
"""
from __future__ import annotations

import asyncio

from app.layers.market_data import get_source
from app.layers.market_data.base import FundSource, PriceSource
from app.schemas import InstrumentCandidate, InstrumentType, RiskLevel


async def enrich(candidates: list[InstrumentCandidate],
                  country: str) -> list[InstrumentCandidate]:
    """Mutate candidates in place with live data; return same list."""
    tasks = [_enrich_one(c, country) for c in candidates]
    await asyncio.gather(*tasks, return_exceptions=True)
    return candidates


async def _enrich_one(c: InstrumentCandidate, country: str) -> None:
    try:
        if c.instrument_type in (InstrumentType.MUTUAL_FUND, InstrumentType.SIP):
            await _enrich_fund(c, country)
        elif c.instrument_type in (InstrumentType.STOCK, InstrumentType.ETF):
            await _enrich_stock(c, country)
    except Exception:
        pass


async def _enrich_fund(c: InstrumentCandidate, country: str) -> None:
    if country != "IN":
        return
    mftool = get_source("mftool")
    if not isinstance(mftool, FundSource):
        return
    matches = await mftool.search(c.name[:30])
    if not matches:
        return
    best = matches[0]
    c.id = f"mftool:{best.scheme_code}"
    c.name = best.scheme_name
    c.category = best.category
    c.provider = best.fund_house or c.provider
    if c.category and "debt" in c.category.lower():
        c.risk_level = RiskLevel.LOW
    elif c.category and "small" in c.category.lower():
        c.risk_level = RiskLevel.VERY_HIGH
    elif c.category and "mid" in c.category.lower():
        c.risk_level = RiskLevel.HIGH
    else:
        c.risk_level = RiskLevel.MODERATE


async def _enrich_stock(c: InstrumentCandidate, country: str) -> None:
    ticker = _guess_ticker(c.name, country)
    if not ticker:
        return
    for src_name in ("yfinance", "nse", "alpha_vantage"):
        src = get_source(src_name)
        if not isinstance(src, PriceSource):
            continue
        quote = await src.get_quote(ticker)
        if not quote:
            continue
        c.id = f"{src_name}:{ticker}"
        c.provider = src_name
        if quote.name and not c.name.startswith(quote.name[:10]):
            c.name = f"{c.name} ({quote.name})"
        c.currency = quote.currency
        break


def _guess_ticker(name: str, country: str) -> str | None:
    name = name.upper().split()[0] if name else ""
    if not name or len(name) > 10:
        return None
    if country == "IN":
        return f"{name}.NS"
    return name
