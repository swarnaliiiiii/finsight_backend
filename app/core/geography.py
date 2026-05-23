"""Geography: country codes drive which data sources are used.

Mobile clients send country code via header `X-Country-Code`. The backend trusts
it (mobile resolves device geolocation -> ISO country on-device).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from fastapi import Header

from app.config import settings

CountryCode = Literal["IN", "US", "UK", "GLOBAL"]
SUPPORTED_COUNTRIES: set[str] = {"IN", "US", "UK"}


class Country(str, Enum):
    INDIA = "IN"
    USA = "US"
    UK = "UK"
    GLOBAL = "GLOBAL"


def normalize_country(raw: str | None) -> CountryCode:
    """Map mobile-provided country code to a supported value, falling back to default."""
    if not raw:
        return settings.DEFAULT_COUNTRY  # type: ignore[return-value]
    code = raw.strip().upper()
    aliases = {"IND": "IN", "INDIA": "IN", "USA": "US", "UNITED STATES": "US",
               "GB": "UK", "GBR": "UK", "UNITED KINGDOM": "UK"}
    code = aliases.get(code, code)
    if code in SUPPORTED_COUNTRIES:
        return code  # type: ignore[return-value]
    return "GLOBAL"


async def country_dependency(
    x_country_code: str | None = Header(default=None, alias="X-Country-Code"),
) -> CountryCode:
    """FastAPI dependency: extracts country code from request header."""
    return normalize_country(x_country_code)


# --- Source routing per country -------------------------------------------------
# These return source NAMES (strings). The actual source instances are resolved
# by the registry to avoid circular imports.

def news_sources_for(country: CountryCode) -> list[str]:
    if country == "IN":
        return ["rss_moneycontrol", "rss_economic_times", "gnews", "marketaux", "tavily"]
    if country == "US":
        return ["finnhub", "newsapi", "marketaux", "gnews", "tavily"]
    if country == "UK":
        return ["newsapi", "marketaux", "gnews", "tavily"]
    return ["finnhub", "marketaux", "gnews", "tavily"]


def price_sources_for(country: CountryCode) -> list[str]:
    if country == "IN":
        return ["nse", "yfinance", "alpha_vantage"]
    return ["yfinance", "alpha_vantage"]


def macro_sources_for(country: CountryCode) -> list[str]:
    if country == "IN":
        return ["rbi", "world_bank"]
    if country == "US":
        return ["fred", "world_bank"]
    if country == "UK":
        return ["world_bank"]
    return ["world_bank"]


def funds_sources_for(country: CountryCode) -> list[str]:
    if country == "IN":
        # AMFI gives the bulk universe; mftool fills per-scheme details.
        return ["amfi", "mftool"]
    return []  # no MF coverage for US/UK in MVP


def market_locale(country: CountryCode) -> dict:
    """Locale info the agents pass into LLM prompts."""
    return {
        "IN": {"currency": "INR", "primary_index": "NIFTY 50", "rate_authority": "RBI", "language": "en-IN"},
        "US": {"currency": "USD", "primary_index": "S&P 500", "rate_authority": "Federal Reserve", "language": "en-US"},
        "UK": {"currency": "GBP", "primary_index": "FTSE 100", "rate_authority": "Bank of England", "language": "en-GB"},
        "GLOBAL": {"currency": "USD", "primary_index": "MSCI World", "rate_authority": "Mixed", "language": "en"},
    }[country]
