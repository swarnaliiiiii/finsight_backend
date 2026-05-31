"""Central source registry. Geography routing in `core/geography.py` returns
source NAMES; this module maps those names to concrete instances.
"""
from __future__ import annotations

from functools import lru_cache

from app.layers.market_data.base import BaseSource
from app.layers.market_data.funds.amfi_source import AMFISource
from app.layers.market_data.funds.mftool_source import MftoolSource
from app.layers.market_data.macro.fred_source import FREDSource
from app.layers.market_data.macro.rbi_source import RBISource
from app.layers.market_data.macro.world_bank_source import WorldBankSource
from app.layers.market_data.news.finnhub_source import FinnhubSource
from app.layers.market_data.news.gnews_source import GNewsSource
from app.layers.market_data.news.marketaux_source import MarketauxSource
from app.layers.market_data.news.newsapi_source import NewsAPISource
from app.layers.market_data.news.rss_source import (EconomicTimesRSSSource,
                                          GenericRSSSource,
                                          MoneycontrolRSSSource)
from app.layers.market_data.news.serp_source import SerpNewsSource
from app.layers.market_data.news.tavily_source import TavilySource
from app.layers.market_data.prices.alpha_vantage_source import AlphaVantageSource
from app.layers.market_data.prices.nse_source import NSESource
from app.layers.market_data.prices.yfinance_source import YFinanceSource


@lru_cache
def _registry() -> dict[str, BaseSource]:
    instances: list[BaseSource] = [
        # prices
        YFinanceSource(), NSESource(), AlphaVantageSource(),
        # news
        FinnhubSource(), NewsAPISource(), MarketauxSource(), GNewsSource(),
        MoneycontrolRSSSource(), EconomicTimesRSSSource(), GenericRSSSource(),
        TavilySource(), SerpNewsSource(),
        # macro
        FREDSource(), RBISource(), WorldBankSource(),
        # funds
        MftoolSource(),
        AMFISource(),
    ]
    return {src.name: src for src in instances}


def get_source(name: str) -> BaseSource | None:
    return _registry().get(name)


def get_sources_by_name(names: list[str]) -> list[BaseSource]:
    reg = _registry()
    return [reg[n] for n in names if n in reg]
