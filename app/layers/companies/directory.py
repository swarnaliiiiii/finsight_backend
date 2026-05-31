"""Curated top-30 companies per country.

Sourced from Nifty 50 (IN), S&P 500 top weights (US), FTSE 100 top weights (UK)
as of late-2025 sector composition. Edit quarterly. The contract — a list of
{ticker, name, sector, country} dicts — is fixed; downstream code reads it.
"""
from __future__ import annotations


_INDIA: list[dict[str, str]] = [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Conglomerate"},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT services"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Private bank"},
    {"ticker": "INFY.NS", "name": "Infosys", "sector": "IT services"},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Private bank"},
    {"ticker": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
    {"ticker": "ITC.NS", "name": "ITC", "sector": "FMCG / Hotels"},
    {"ticker": "SBIN.NS", "name": "State Bank of India", "sector": "PSU bank"},
    {"ticker": "LT.NS", "name": "Larsen & Toubro", "sector": "Engineering / Construction"},
    {"ticker": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "FMCG"},
    {"ticker": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "NBFC"},
    {"ticker": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Private bank"},
    {"ticker": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Auto"},
    {"ticker": "AXISBANK.NS", "name": "Axis Bank", "sector": "Private bank"},
    {"ticker": "ASIANPAINT.NS", "name": "Asian Paints", "sector": "Paints"},
    {"ticker": "SUNPHARMA.NS", "name": "Sun Pharmaceutical", "sector": "Pharma"},
    {"ticker": "TITAN.NS", "name": "Titan Company", "sector": "Consumer durables"},
    {"ticker": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Cement"},
    {"ticker": "NESTLEIND.NS", "name": "Nestle India", "sector": "FMCG"},
    {"ticker": "WIPRO.NS", "name": "Wipro", "sector": "IT services"},
    {"ticker": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT services"},
    {"ticker": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Conglomerate"},
    {"ticker": "POWERGRID.NS", "name": "Power Grid Corporation", "sector": "Power transmission"},
    {"ticker": "NTPC.NS", "name": "NTPC", "sector": "Power generation"},
    {"ticker": "ONGC.NS", "name": "Oil & Natural Gas Corp", "sector": "Oil & gas"},
    {"ticker": "TATAMOTORS.NS", "name": "Tata Motors", "sector": "Auto"},
    {"ticker": "JSWSTEEL.NS", "name": "JSW Steel", "sector": "Steel"},
    {"ticker": "TATASTEEL.NS", "name": "Tata Steel", "sector": "Steel"},
    {"ticker": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Auto / Farm equipment"},
    {"ticker": "INDUSINDBK.NS", "name": "IndusInd Bank", "sector": "Private bank"},
]


_US: list[dict[str, str]] = [
    {"ticker": "AAPL", "name": "Apple", "sector": "Tech hardware"},
    {"ticker": "MSFT", "name": "Microsoft", "sector": "Software / Cloud"},
    {"ticker": "NVDA", "name": "NVIDIA", "sector": "Semiconductors / AI"},
    {"ticker": "AMZN", "name": "Amazon", "sector": "E-commerce / Cloud"},
    {"ticker": "GOOGL", "name": "Alphabet", "sector": "Internet / Ads"},
    {"ticker": "META", "name": "Meta Platforms", "sector": "Social / Ads"},
    {"ticker": "TSLA", "name": "Tesla", "sector": "Auto / Energy"},
    {"ticker": "BRK-B", "name": "Berkshire Hathaway", "sector": "Conglomerate"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Bank"},
    {"ticker": "V", "name": "Visa", "sector": "Payments"},
    {"ticker": "MA", "name": "Mastercard", "sector": "Payments"},
    {"ticker": "UNH", "name": "UnitedHealth Group", "sector": "Health insurance"},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Pharma"},
    {"ticker": "PG", "name": "Procter & Gamble", "sector": "Consumer staples"},
    {"ticker": "XOM", "name": "ExxonMobil", "sector": "Oil & gas"},
    {"ticker": "HD", "name": "Home Depot", "sector": "Retail"},
    {"ticker": "COST", "name": "Costco Wholesale", "sector": "Retail"},
    {"ticker": "ABBV", "name": "AbbVie", "sector": "Pharma"},
    {"ticker": "KO", "name": "Coca-Cola", "sector": "Beverages"},
    {"ticker": "PEP", "name": "PepsiCo", "sector": "Beverages / Snacks"},
    {"ticker": "AVGO", "name": "Broadcom", "sector": "Semiconductors"},
    {"ticker": "CVX", "name": "Chevron", "sector": "Oil & gas"},
    {"ticker": "WMT", "name": "Walmart", "sector": "Retail"},
    {"ticker": "MRK", "name": "Merck", "sector": "Pharma"},
    {"ticker": "BAC", "name": "Bank of America", "sector": "Bank"},
    {"ticker": "MCD", "name": "McDonald's", "sector": "Restaurants"},
    {"ticker": "ADBE", "name": "Adobe", "sector": "Software"},
    {"ticker": "CRM", "name": "Salesforce", "sector": "Software / Cloud"},
    {"ticker": "NFLX", "name": "Netflix", "sector": "Streaming media"},
    {"ticker": "DIS", "name": "Walt Disney", "sector": "Media / Theme parks"},
]


_UK: list[dict[str, str]] = [
    {"ticker": "AZN.L", "name": "AstraZeneca", "sector": "Pharma"},
    {"ticker": "SHEL.L", "name": "Shell", "sector": "Oil & gas"},
    {"ticker": "HSBA.L", "name": "HSBC Holdings", "sector": "Bank"},
    {"ticker": "ULVR.L", "name": "Unilever", "sector": "Consumer goods"},
    {"ticker": "BP.L", "name": "BP", "sector": "Oil & gas"},
    {"ticker": "GSK.L", "name": "GSK", "sector": "Pharma"},
    {"ticker": "RIO.L", "name": "Rio Tinto", "sector": "Mining"},
    {"ticker": "DGE.L", "name": "Diageo", "sector": "Beverages"},
    {"ticker": "REL.L", "name": "RELX", "sector": "Information services"},
    {"ticker": "LSEG.L", "name": "London Stock Exchange Group", "sector": "Financial data"},
    {"ticker": "BARC.L", "name": "Barclays", "sector": "Bank"},
    {"ticker": "LLOY.L", "name": "Lloyds Banking Group", "sector": "Bank"},
    {"ticker": "GLEN.L", "name": "Glencore", "sector": "Mining / Trading"},
    {"ticker": "TSCO.L", "name": "Tesco", "sector": "Retail"},
    {"ticker": "VOD.L", "name": "Vodafone Group", "sector": "Telecom"},
    {"ticker": "BATS.L", "name": "British American Tobacco", "sector": "Tobacco"},
    {"ticker": "PRU.L", "name": "Prudential", "sector": "Insurance"},
    {"ticker": "NG.L", "name": "National Grid", "sector": "Utilities"},
    {"ticker": "STAN.L", "name": "Standard Chartered", "sector": "Bank"},
    {"ticker": "AAL.L", "name": "Anglo American", "sector": "Mining"},
]


_TABLES = {"IN": _INDIA, "US": _US, "UK": _UK}


def list_companies(country: str = "IN", limit: int = 30) -> list[dict[str, str]]:
    table = _TABLES.get(country, _INDIA)
    return [{**row, "country": country} for row in table[:limit]]
