"""Curated registry of historical eras.

Each entry is a named window with start/end dates and category tags. The
list is intentionally short — focused on windows beginners actually ask
about. Adding a new era = one entry; no other changes needed.

Country tagging is permissive: an empty `countries` list means the era
applied globally enough to be relevant everywhere.
"""
from __future__ import annotations

from datetime import date

from app.schemas import Era


ERAS: list[Era] = [
    Era(
        id="covid_crash_2020",
        label="COVID crash (Feb–Mar 2020)",
        start_date=date(2020, 2, 1),
        end_date=date(2020, 4, 30),
        countries=[],
        categories=["pandemic", "crash", "covid"],
        summary=("Global markets fell sharply as COVID-19 spread. NIFTY 50 "
                  "lost ~38% peak-to-trough before recovering."),
    ),
    Era(
        id="covid_recovery_2020_21",
        label="COVID recovery rally (Apr 2020–Dec 2021)",
        start_date=date(2020, 4, 1),
        end_date=date(2021, 12, 31),
        countries=[],
        categories=["recovery", "covid", "bull"],
        summary=("Equity indices roughly doubled from the March 2020 lows, "
                  "led by tech and consumer names."),
    ),
    Era(
        id="gfc_2008",
        label="Global Financial Crisis (2008)",
        start_date=date(2008, 1, 1),
        end_date=date(2009, 3, 31),
        countries=[],
        categories=["crash", "gfc", "2008", "financial_crisis"],
        summary=("Global equity benchmarks lost 40–60% peak-to-trough. "
                  "NIFTY 50 fell ~60% from its January 2008 high."),
    ),
    Era(
        id="taper_tantrum_2013",
        label="Taper tantrum (May–Sep 2013)",
        start_date=date(2013, 5, 1),
        end_date=date(2013, 9, 30),
        countries=[],
        categories=["em_selloff", "rate_shock", "taper"],
        summary=("Fed signalled QE tapering; emerging-market currencies and "
                  "bonds sold off sharply. INR hit a fresh low against USD."),
    ),
    Era(
        id="demonetisation_2016",
        label="Indian demonetisation (Nov 2016–Jan 2017)",
        start_date=date(2016, 11, 8),
        end_date=date(2017, 1, 31),
        countries=["IN"],
        categories=["india_specific", "policy", "demonetisation"],
        summary=("Govt withdrew ₹500/₹1000 notes. Initial equity wobble "
                  "followed by a strong recovery."),
    ),
    Era(
        id="rate_hike_2022",
        label="2022 global rate-hike cycle",
        start_date=date(2022, 3, 1),
        end_date=date(2023, 7, 31),
        countries=[],
        categories=["rate_shock", "inflation", "monetary_policy", "2022"],
        summary=("Aggressive Fed/RBI hikes against persistent inflation. "
                  "Growth-stock heavy indices underperformed; value rotated in."),
    ),
    Era(
        id="india_election_rally_2024",
        label="2024 Indian election cycle",
        start_date=date(2024, 4, 1),
        end_date=date(2024, 8, 31),
        countries=["IN"],
        categories=["india_specific", "election", "2024"],
        summary=("Markets volatile around the general-election counting day "
                  "(June 4), then rallied to fresh highs."),
    ),
]


def get_era(era_id: str) -> Era | None:
    for e in ERAS:
        if e.id == era_id:
            return e
    return None
