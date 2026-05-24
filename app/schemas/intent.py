"""Intent enum: the closed set of query types the orchestrator can route.

The Intent agent classifies a free-form NL query into exactly one Intent. The
orchestrator's INTENT_PLANS registry maps each Intent to a deterministic plan.

Adding a new query type means: add an Intent, add a plan, ship. No agent
decides what to do — the plan decides.
"""
from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    EXPLAIN_TERM = "explain_term"
    COMPARE_INSTRUMENTS = "compare_instruments"
    RECOMMEND_INSTRUMENT = "recommend_instrument"
    PROJECT_RETURNS = "project_returns"
    CURRENT_NEWS = "current_news"
    HISTORICAL_BEHAVIOR = "historical_behavior"
    QUICK_FACT = "quick_fact"
    DAILY_BRIEF = "daily_brief"
    INSTRUMENT_STARTER = "instrument_starter"
    UNKNOWN = "unknown"
