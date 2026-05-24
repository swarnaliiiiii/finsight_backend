"""Curated beginner picks per (country, instrument).

Safety-net data so the recommender layer always returns a non-empty list,
even when scraping fails or sites are unreachable. Sourced from public
AMFI / SEBI / NSE / Bogleheads reading. Not a recommendation — these are
the names a beginner usually encounters as they research.

Update this list quarterly; the contract (list[InstrumentCandidate]) is
the same as the scraping path.
"""
from __future__ import annotations

from app.schemas import InstrumentCandidate, InstrumentType, RiskLevel

# Each entry: (id_slug, display_name, provider, category, risk, currency,
#              detail_url, review_summary)
_INDIA: dict[InstrumentType, list[tuple[str, str, str, str | None,
                                         RiskLevel | None, str | None,
                                         str | None]]] = {
    InstrumentType.SIP: [
        ("uti-nifty-50-index",  "UTI Nifty 50 Index Fund — Direct Growth",
         "UTI",  "Large-cap index",  RiskLevel.MODERATE,
         "https://www.utimf.com/", "Tracks Nifty 50. Low cost, broad-market exposure."),
        ("hdfc-index-nifty-50", "HDFC Index Fund Nifty 50 Plan — Direct Growth",
         "HDFC AMC",  "Large-cap index", RiskLevel.MODERATE,
         "https://www.hdfcfund.com/", "One of the largest passive funds in India."),
        ("icici-pru-bluechip", "ICICI Prudential Bluechip Fund — Direct Growth",
         "ICICI Prudential", "Large-cap active", RiskLevel.MODERATE,
         "https://www.icicipruamc.com/", "Veteran active large-cap with long track record."),
        ("parag-parikh-flexi-cap", "Parag Parikh Flexi Cap Fund — Direct Growth",
         "PPFAS", "Flexi-cap (with intl. tilt)", RiskLevel.HIGH,
         "https://amc.ppfas.com/", "Beginner-friendly flexi-cap with international diversification."),
        ("mirae-large-midcap", "Mirae Asset Large & Midcap Fund — Direct Growth",
         "Mirae Asset", "Large & Midcap", RiskLevel.HIGH,
         "https://www.miraeassetmf.co.in/", "Balances steady large-caps with growth-oriented midcaps."),
    ],
    InstrumentType.MUTUAL_FUND: [
        ("uti-nifty-50-index", "UTI Nifty 50 Index Fund — Direct Growth",
         "UTI", "Large-cap index", RiskLevel.MODERATE, None,
         "Tracks Nifty 50. Low cost. Most-bought beginner fund."),
        ("parag-parikh-flexi-cap", "Parag Parikh Flexi Cap Fund — Direct Growth",
         "PPFAS", "Flexi-cap", RiskLevel.HIGH, None,
         "Diversified active fund with international tilt."),
        ("icici-pru-bluechip", "ICICI Prudential Bluechip Fund — Direct Growth",
         "ICICI Prudential", "Large-cap active", RiskLevel.MODERATE, None,
         "Stable large-cap workhorse."),
        ("sbi-magnum-medium-duration", "SBI Magnum Medium Duration Fund — Direct Growth",
         "SBI Mutual Fund", "Debt — medium duration", RiskLevel.LOW, None,
         "Beginner-friendly debt option."),
        ("hdfc-balanced-advantage", "HDFC Balanced Advantage Fund — Direct Growth",
         "HDFC AMC", "Hybrid — balanced advantage", RiskLevel.MODERATE, None,
         "Auto-rebalances between equity and debt based on valuations."),
    ],
    InstrumentType.ETF: [
        ("nippon-nifty-50-etf", "Nippon India Nifty 50 BeES",
         "Nippon India", "Nifty 50 index ETF", RiskLevel.MODERATE,
         "https://mf.nipponindiaim.com/", "Oldest and most-traded Nifty 50 ETF in India."),
        ("sbi-nifty-50-etf", "SBI Nifty 50 ETF",
         "SBI Mutual Fund", "Nifty 50 index ETF", RiskLevel.MODERATE, None,
         "Largest Nifty 50 ETF by AUM."),
        ("nippon-gold-etf", "Nippon India Gold ETF (GOLDBEES)",
         "Nippon India", "Gold ETF", RiskLevel.MODERATE,
         "https://mf.nipponindiaim.com/", "Most-bought gold ETF — physical gold-backed."),
        ("nippon-silver-etf", "Nippon India Silver ETF (SILVERBEES)",
         "Nippon India", "Silver ETF", RiskLevel.HIGH, None,
         "Silver ETF — more volatile than gold but industrial demand kicker."),
        ("motilal-nasdaq-100", "Motilal Oswal NASDAQ 100 ETF",
         "Motilal Oswal", "International equity ETF", RiskLevel.HIGH, None,
         "Cheapest way for an Indian retail investor to own US tech."),
    ],
    InstrumentType.STOCK: [
        ("reliance", "Reliance Industries",
         "NSE/BSE: RELIANCE", "Energy / Telecom / Retail conglomerate",
         RiskLevel.MODERATE, None, "India's largest listed company by market cap."),
        ("tcs", "Tata Consultancy Services",
         "NSE/BSE: TCS", "IT services", RiskLevel.MODERATE, None,
         "Largest Indian IT services firm; consistent dividend payer."),
        ("hdfc-bank", "HDFC Bank",
         "NSE/BSE: HDFCBANK", "Private bank", RiskLevel.MODERATE, None,
         "India's largest private bank."),
        ("infosys", "Infosys",
         "NSE/BSE: INFY", "IT services", RiskLevel.MODERATE, None,
         "Second-largest Indian IT services firm."),
        ("itc", "ITC",
         "NSE/BSE: ITC", "FMCG / Cigarettes / Hotels", RiskLevel.LOW, None,
         "Defensive cash-flow business; high dividend yield."),
    ],
    InstrumentType.BOND: [
        ("g-sec-10y", "Government of India 10-year G-Sec",
         "RBI Retail Direct", "Sovereign bond", RiskLevel.LOW,
         "https://rbiretaildirect.org.in/",
         "Lowest-risk INR fixed income; bought directly from RBI Retail Direct."),
        ("sgb-2024-25", "Sovereign Gold Bond (latest tranche)",
         "RBI", "Gold-linked sovereign bond", RiskLevel.LOW,
         "https://rbiretaildirect.org.in/",
         "Pays 2.5% interest + tracks gold price. Tax-free at maturity."),
        ("sdl-state-dev-loan", "State Development Loan (SDL)",
         "RBI Retail Direct", "Sub-sovereign", RiskLevel.LOW, None,
         "Slightly higher yield than central G-Secs."),
        ("hdfc-corporate-bond", "HDFC Corporate Bond Fund — Direct Growth",
         "HDFC AMC", "Corporate bond fund", RiskLevel.LOW, None,
         "Diversified high-grade corporate debt fund."),
    ],
    InstrumentType.NCD: [
        ("muthoot-ncd", "Muthoot Finance NCD (latest series)",
         "Muthoot Finance", "AA-rated NBFC NCD", RiskLevel.MODERATE, None,
         "Listed retail NCD with quarterly/monthly coupons."),
        ("shriram-finance-ncd", "Shriram Finance NCD (latest series)",
         "Shriram Finance", "AA-rated NBFC NCD", RiskLevel.MODERATE, None,
         "Listed retail NCD popular with income-seeking investors."),
    ],
    InstrumentType.FD: [
        ("sbi-fd",  "SBI Term Deposit (Senior Citizen rates apply)",
         "SBI", "Bank FD", RiskLevel.LOW, "https://sbi.co.in/",
         "Largest PSB; insured up to ₹5 lakh under DICGC."),
        ("hdfc-fd", "HDFC Bank Fixed Deposit",
         "HDFC Bank", "Bank FD", RiskLevel.LOW, None,
         "Premium private bank FD with competitive rates for tenor >2y."),
        ("bajaj-finance-fd", "Bajaj Finance FD (AAA-rated)",
         "Bajaj Finance", "Corporate FD", RiskLevel.LOW, None,
         "Higher rate than bank FDs; AAA-rated corporate FD."),
        ("post-office-mis", "Post Office Monthly Income Scheme (MIS)",
         "India Post", "Sovereign-backed savings", RiskLevel.LOW, None,
         "Backed by Government of India. Monthly payouts."),
    ],
}


_US: dict[InstrumentType, list[tuple]] = {
    InstrumentType.SIP: [
        ("vti", "Vanguard Total Stock Market (VTI)",
         "Vanguard", "Total-market ETF", RiskLevel.MODERATE,
         "https://investor.vanguard.com/etf/profile/VTI",
         "The default beginner US equity holding. Ultra-low cost."),
        ("voo", "Vanguard S&P 500 (VOO)",
         "Vanguard", "Large-cap index", RiskLevel.MODERATE, None,
         "S&P 500 in one ticker."),
        ("vt", "Vanguard Total World (VT)",
         "Vanguard", "Global equity", RiskLevel.MODERATE, None,
         "One-ticker global diversification."),
    ],
    InstrumentType.ETF: [
        ("voo", "Vanguard S&P 500 (VOO)",
         "Vanguard", "Large-cap index", RiskLevel.MODERATE, None,
         "Most-bought S&P 500 ETF by beginners."),
        ("qqq", "Invesco QQQ (Nasdaq-100)",
         "Invesco", "Tech-heavy growth", RiskLevel.HIGH, None,
         "Top 100 non-financial Nasdaq names."),
        ("vti", "Vanguard Total Stock Market (VTI)",
         "Vanguard", "Total-market ETF", RiskLevel.MODERATE, None,
         "Broader than VOO — includes mid/small caps."),
        ("gld", "SPDR Gold Shares (GLD)",
         "State Street", "Gold ETF", RiskLevel.MODERATE, None,
         "Largest physical-gold ETF in the world."),
        ("slv", "iShares Silver Trust (SLV)",
         "BlackRock", "Silver ETF", RiskLevel.HIGH, None,
         "Largest silver ETF — more volatile than gold."),
    ],
}


_UK: dict[InstrumentType, list[tuple]] = {
    InstrumentType.SIP: [
        ("vwrl", "Vanguard FTSE All-World (VWRL)",
         "Vanguard", "Global equity ETF", RiskLevel.MODERATE, None,
         "Default beginner global equity holding on UK platforms."),
        ("vusa", "Vanguard S&P 500 (VUSA)",
         "Vanguard", "US large-cap", RiskLevel.MODERATE, None,
         "S&P 500 exposure in GBP."),
    ],
    InstrumentType.ETF: [
        ("vwrl", "Vanguard FTSE All-World (VWRL)",
         "Vanguard", "Global equity ETF", RiskLevel.MODERATE, None,
         "Most-bought global ETF on UK platforms."),
        ("isf", "iShares FTSE 100 (ISF)",
         "BlackRock", "UK large-cap", RiskLevel.MODERATE, None,
         "FTSE 100 in one ticker."),
    ],
}


def curated_candidates(instrument: InstrumentType, country: str,
                          limit: int = 5) -> list[InstrumentCandidate]:
    """Return a small curated list of beginner-friendly picks. Always
    non-empty for the (country, instrument) pairs we know about."""
    table = (_INDIA if country == "IN"
              else _US if country == "US"
              else _UK if country == "UK"
              else {})
    entries = table.get(instrument, [])
    out: list[InstrumentCandidate] = []
    currency = "INR" if country == "IN" else "USD" if country == "US" else "GBP"
    for idx, row in enumerate(entries[:limit]):
        slug, name, provider, category, risk, url, summary = row
        out.append(InstrumentCandidate(
            id=f"curated:{country.lower()}:{slug}",
            name=name,
            instrument_type=instrument,
            provider=provider,
            category=category,
            consensus_rank=idx + 1,
            consensus_sources=["curated"],
            risk_level=risk,
            detail_url=url,
            review_summary=summary,
            currency=currency,
        ))
    return out
