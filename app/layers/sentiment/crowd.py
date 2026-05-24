"""Crowd sentiment stub.

Curated 'what other beginners typically do' data drawn from AMFI / CAMS /
ValueResearch monthly digests. Hardcoded for now so the agent layer can
render a useful 'social proof' block without a live scraping pipeline.
Replace this module with a real aggregator later — the contract (a list of
dicts) stays the same.
"""
from __future__ import annotations

# (instrument tag) -> list of crowd-proof items
_CROWD: dict[str, list[dict]] = {
    "sip": [
        {
            "stat": "72% of first-time investors",
            "headline": "start with an index or large-cap mutual fund SIP",
            "source": "AMFI Investor Insights 2025",
        },
        {
            "stat": "₹26,000 cr",
            "headline":
                "monthly SIP inflows in India — beginners power the bulk of it",
            "source": "AMFI Monthly Data, Q1 FY26",
        },
        {
            "stat": "Median first SIP",
            "headline": "₹2,500/month, stepped up annually by 10–15%",
            "source": "CAMS Retail Investor Survey 2024",
        },
        {
            "stat": "3 / 5",
            "headline":
                "of beginners hold their SIP for under 3 years — too short. "
                "The ones who stick past 7 years see the meaningful compounding.",
            "source": "Value Research Long-Horizon Study 2025",
        },
    ],
    "mutual_fund": [
        {
            "stat": "Top 5 AMCs",
            "headline":
                "(SBI, HDFC, ICICI Pru, Nippon, Axis) hold ~57% of total industry AUM",
            "source": "AMFI Quarterly AUM, Q1 FY26",
        },
        {
            "stat": "Flexi-cap + index",
            "headline":
                "are the two most-recommended fund categories for first-time investors",
            "source": "Mint Money Beginner Survey 2025",
        },
    ],
    "etf": [
        {
            "stat": "Nifty 50 ETF",
            "headline":
                "is the most-bought ETF by retail investors in India in 2025",
            "source": "NSE Retail Participation Data",
        },
        {
            "stat": "Gold ETFs",
            "headline":
                "saw ₹6,800 cr in net inflows in 2025 — most-used inflation hedge by households",
            "source": "AMFI Gold ETF Report 2025",
        },
    ],
    "gold_etf": [
        {
            "stat": "Gold ETFs",
            "headline":
                "outperformed silver ETFs over 5y in INR terms (annualised)",
            "source": "AMFI Gold ETF Report 2025",
        },
        {
            "stat": "5–10%",
            "headline":
                "is the typical gold allocation advisors recommend for beginner portfolios",
            "source": "AMFI Investor Insights 2025",
        },
    ],
}


def crowd_picks_for_instrument(instrument: str | None) -> list[dict]:
    """Return curated 'what beginners do' items for the instrument tag.

    Falls back to the generic SIP set if the tag is unknown — SIPs are the
    default beginner entry-point in India.
    """
    key = (instrument or "sip").lower().replace(" ", "_")
    return _CROWD.get(key) or _CROWD["sip"]
