"""Signal gatherers: market pulse, macro changes, trending stocks.

Each returns a list of structured candidate signals that the Daily Brief
agent will score, rank, and explain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.layers.market_data import get_source
from app.layers.market_data.base import MacroSource, NewsSource, PriceSource
from app.schemas import BriefSeverity, BriefSourceType, InstrumentType

_COUNTRY_INDEX_TICKER: dict[str, str] = {
    "IN": "^NSEI",
    "US": "^GSPC",
    "UK": "^FTSE",
}


@dataclass
class Signal:
    """Internal candidate signal before LLM polishing."""
    title: str
    raw_data: str
    source_type: BriefSourceType
    affected_instruments: list[InstrumentType] = field(default_factory=list)
    severity: BriefSeverity = BriefSeverity.INFO
    source_links: list[str] = field(default_factory=list)
    learn_more_terms: list[str] = field(default_factory=list)
    importance_score: float = 0.5


async def market_pulse(country: str) -> Signal | None:
    """Returns a signal describing today's index movement for the country."""
    ticker = _COUNTRY_INDEX_TICKER.get(country)
    if not ticker:
        return None
    yf = get_source("yfinance")
    if not isinstance(yf, PriceSource):
        return None
    quote = await yf.get_quote(ticker)
    if not quote:
        return None
    pct = quote.change_percent
    abs_pct = abs(pct)
    if abs_pct >= 2.0:
        severity = BriefSeverity.IMPORTANT
        importance = 0.95
    elif abs_pct >= 1.0:
        severity = BriefSeverity.WATCH
        importance = 0.8
    else:
        severity = BriefSeverity.INFO
        importance = 0.5
    direction = "up" if pct > 0 else "down" if pct < 0 else "flat"
    return Signal(
        title=f"{quote.name or ticker} {direction} {abs_pct:.2f}% today",
        raw_data=f"Index {ticker} ({quote.name or 'primary index'}): "
                  f"{quote.price:.2f} {quote.currency}, change {pct:+.2f}%",
        source_type=BriefSourceType.INDEX,
        affected_instruments=[InstrumentType.SIP, InstrumentType.MUTUAL_FUND,
                               InstrumentType.STOCK, InstrumentType.ETF],
        severity=severity,
        importance_score=importance,
        learn_more_terms=["sip", "mutual_fund", "etf"],
    )


async def macro_movements(country: str) -> list[Signal]:
    """Surface notable macro indicators (repo/Fed rate, CPI, etc.)."""
    sources = [s for s in (get_source("rbi"), get_source("fred"),
                            get_source("world_bank"))
               if isinstance(s, MacroSource)]
    signals: list[Signal] = []
    for src in sources:
        try:
            points = await src.get_indicators(country)
        except Exception:
            continue
        for p in points:
            instruments, severity, importance, terms = _classify_macro(p.indicator)
            if not instruments:
                continue
            signals.append(Signal(
                title=f"{p.indicator}: {p.value:.2f} {p.unit or ''}".strip(),
                raw_data=f"{p.indicator} = {p.value} {p.unit or ''} (as of {p.as_of})",
                source_type=BriefSourceType.MACRO,
                affected_instruments=instruments,
                severity=severity,
                importance_score=importance,
                learn_more_terms=terms,
            ))
    return signals


def _classify_macro(indicator: str) -> tuple[list[InstrumentType], BriefSeverity, float, list[str]]:
    name = indicator.lower()
    if "repo" in name or "fed funds" in name:
        return ([InstrumentType.BOND, InstrumentType.FD, InstrumentType.NCD,
                  InstrumentType.SIP], BriefSeverity.WATCH, 0.85,
                ["bond", "fd", "sip"])
    if "inflation" in name or "cpi" in name:
        return ([InstrumentType.FD, InstrumentType.BOND, InstrumentType.SIP],
                BriefSeverity.WATCH, 0.75, ["fd", "bond"])
    if "treasury" in name or "yield" in name:
        return ([InstrumentType.BOND, InstrumentType.NCD],
                BriefSeverity.INFO, 0.6, ["bond", "ncd"])
    if "unemployment" in name:
        return ([InstrumentType.STOCK, InstrumentType.ETF],
                BriefSeverity.INFO, 0.5, ["stock", "etf"])
    return ([], BriefSeverity.INFO, 0.3, [])


async def trending_news(country: str, *, limit: int = 8) -> list[Signal]:
    """Pull recent news with sentiment from Marketaux (and fall back to others)."""
    signals: list[Signal] = []
    for src_name in ("marketaux", "finnhub", "newsapi"):
        src = get_source(src_name)
        if not isinstance(src, NewsSource):
            continue
        try:
            items = await src.fetch_news(country=country, limit=limit)
        except Exception:
            continue
        for item in items:
            if not item.title:
                continue
            score = item.sentiment_score or 0.0
            severity = (BriefSeverity.IMPORTANT if abs(score) > 0.5
                         else BriefSeverity.WATCH if abs(score) > 0.2
                         else BriefSeverity.INFO)
            importance = min(1.0, 0.4 + abs(score) * 0.6)
            affected: list[InstrumentType] = []
            if item.tickers:
                affected = [InstrumentType.STOCK, InstrumentType.ETF]
            signals.append(Signal(
                title=item.title[:140],
                raw_data=f"{item.title} | sentiment={score:+.2f} | "
                          f"tickers={item.tickers[:3]}",
                source_type=BriefSourceType.SENTIMENT if score else BriefSourceType.NEWS,
                affected_instruments=affected,
                severity=severity,
                source_links=[item.url] if item.url else [],
                importance_score=importance,
                learn_more_terms=["stock", "etf"] if item.tickers else [],
            ))
        if signals:
            break
    return signals[:limit]
