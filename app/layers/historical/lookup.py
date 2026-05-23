"""Lookup helpers: free-form text -> Era + representative ticker.

The user types things like "how did gold behave in 2008" or "small cap
during COVID". We match:
  - explicit category keywords (covid, gfc, 2008, taper, demonetisation, ...)
  - a year/year-range if mentioned
  - a country bias (preferring India-tagged eras when the user is on IN)

For instruments, we resolve a category mention ("gold", "small cap") to a
representative ticker per country. If the user mentioned a specific ticker
verbatim, we use that instead.
"""
from __future__ import annotations

import re

from app.layers.historical.eras import ERAS
from app.schemas import Era

# --- era matching ---------------------------------------------------------

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def find_era(query: str, *, country: str = "IN") -> Era | None:
    """Best-effort match of `query` to one of the curated ERAS. Returns the
    most specific match or None."""
    q = query.lower()

    # 1. Direct category keyword match.
    direct: list[tuple[int, Era]] = []
    for era in ERAS:
        hits = sum(1 for cat in era.categories if cat in q)
        if hits:
            direct.append((hits, era))

    # 2. Year overlap.
    years = {int(m.group(0)) for m in _YEAR_RE.finditer(q)}
    year_matched: list[Era] = []
    if years:
        for era in ERAS:
            era_years = set(range(era.start_date.year, era.end_date.year + 1))
            if era_years & years:
                year_matched.append(era)

    # 3. Country bias.
    def country_bonus(era: Era) -> int:
        if country in era.countries:
            return 1
        if not era.countries:
            return 0
        return -1

    if direct:
        direct.sort(key=lambda t: (t[0], country_bonus(t[1])), reverse=True)
        return direct[0][1]
    if year_matched:
        year_matched.sort(key=lambda e: (country_bonus(e),
                                            len(e.categories)), reverse=True)
        return year_matched[0]
    return None


# --- ticker proxy resolution ---------------------------------------------

# Conventional representative tickers per category, per country.
_CATEGORY_TICKERS: dict[str, dict[str, str]] = {
    "IN": {
        "nifty": "^NSEI",
        "sensex": "^BSESN",
        "gold": "GOLDBEES.NS",
        "silver": "SILVERBEES.NS",
        "small_cap": "^CNXSC",
        "mid_cap": "^CNXMID",
        "large_cap": "^NSEI",
        "bank": "^NSEBANK",
        "it": "^CNXIT",
        "bonds": "GILT5YBEES.NS",
    },
    "US": {
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "gold": "GLD",
        "silver": "SLV",
        "small_cap": "^RUT",
        "bonds": "TLT",
    },
    "UK": {
        "ftse": "^FTSE",
        "gold": "PHGP.L",
    },
}

# Heuristic mapping from free-form phrasing to the category key above.
_PHRASE_TO_CATEGORY: list[tuple[str, str]] = [
    ("small cap", "small_cap"), ("small-cap", "small_cap"),
    ("smallcap", "small_cap"),
    ("mid cap", "mid_cap"), ("mid-cap", "mid_cap"), ("midcap", "mid_cap"),
    ("large cap", "large_cap"), ("large-cap", "large_cap"),
    ("largecap", "large_cap"),
    ("gold etf", "gold"), ("gold", "gold"),
    ("silver etf", "silver"), ("silver", "silver"),
    ("nifty", "nifty"), ("sensex", "sensex"),
    ("nasdaq", "nasdaq"), ("s&p", "sp500"), ("s&p 500", "sp500"),
    ("ftse", "ftse"),
    ("bond", "bonds"), ("g-sec", "bonds"), ("gilt", "bonds"),
    ("banking", "bank"), ("bank index", "bank"),
    ("it index", "it"), ("tech", "it"),
]


def resolve_ticker(query_or_hint: str, country: str = "IN"
                    ) -> tuple[str | None, str]:
    """Map a free-form mention ('gold ETFs', 'small cap funds') to a
    representative ticker for that country. Returns (ticker, human_label)."""
    q = query_or_hint.lower()

    # Explicit ticker pattern? (e.g. RELIANCE.NS, ^NSEI, GOLDBEES.NS, GLD)
    m = re.search(r"\b\^?[A-Z]{2,8}(?:\.[A-Z]{1,3})?\b", query_or_hint)
    if m and not m.group(0).lower() in q.split():
        # we matched something with caps; trust it as a ticker.
        ticker = m.group(0)
        return ticker, ticker

    table = _CATEGORY_TICKERS.get(country, {})
    for phrase, cat in _PHRASE_TO_CATEGORY:
        if phrase in q and cat in table:
            return table[cat], _label_for_category(cat, country, table[cat])
    return None, "unspecified instrument"


def _label_for_category(cat: str, country: str, ticker: str) -> str:
    pretty = {
        "small_cap": "Small-cap index",
        "mid_cap": "Mid-cap index",
        "large_cap": "Large-cap / NIFTY 50",
        "gold": "Gold ETF",
        "silver": "Silver ETF",
        "nifty": "NIFTY 50",
        "sensex": "BSE Sensex",
        "nasdaq": "NASDAQ Composite",
        "sp500": "S&P 500",
        "ftse": "FTSE 100",
        "bonds": "Bond proxy",
        "bank": "Bank Nifty",
        "it": "IT index",
    }.get(cat, cat)
    return f"{pretty} (proxy: {ticker})"


def ticker_label_for(ticker: str) -> str:
    """Reverse lookup so the agent can show a friendly label when only the
    ticker was resolved."""
    for country, table in _CATEGORY_TICKERS.items():
        for cat, t in table.items():
            if t == ticker:
                return _label_for_category(cat, country, ticker)
    return ticker
