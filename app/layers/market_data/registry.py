"""Central source registry. Geography routing in `core/geography.py` returns
source NAMES; this module maps those names to concrete instances.
"""
from __future__ import annotations

from functools import lru_cache

from app.sources.base import BaseSource
from app.sources.funds.mftool_source import MftoolSource
from app.sources.macro.fred_source import FREDSource
from app.sources.macro.rbi_source import RBISource
from app.sources.macro.world_bank_source import WorldBankSource
from app.sources.news.finnhub_source import FinnhubSource
from app.sources.news.gnews_source import GNewsSource
from app.sources.news.marketaux_source import MarketauxSource
from app.sources.news.newsapi_source import NewsAPISource
from app.sources.news.rss_source import (EconomicTimesRSSSource,
                                          GenericRSSSource,
                                          MoneycontrolRSSSource)
from app.sources.news.tavily_source import TavilySource
from app.sources.prices.alpha_vantage_source import AlphaVantageSource
from app.sources.prices.nse_source import NSESource
from app.sources.prices.yfinance_source import YFinanceSource


@lru_cache
def _registry() -> dict[str, BaseSource]:
    instances: list[BaseSource] = [
        # prices
        YFinanceSource(), NSESource(), AlphaVantageSource(),
        # news
        FinnhubSource(), NewsAPISource(), MarketauxSource(), GNewsSource(),
        MoneycontrolRSSSource(), EconomicTimesRSSSource(), GenericRSSSource(),
        TavilySource(),
        # macro
        FREDSource(), RBISource(), WorldBankSource(),
        # funds
        MftoolSource(),
    ]
    return {src.name: src for src in instances}


def get_source(name: str) -> BaseSource | None:
    return _registry().get(name)


def get_sources_by_name(names: list[str]) -> list[BaseSource]:
    reg = _registry()
    return [reg[n] for n in names if n in reg]
