"""Historical Analytics layer.

Three responsibilities:
  - ERAS  : curated list of named historical windows (COVID, GFC, etc.)
  - lookup: matchers that turn free-form text into an Era + ticker proxy
  - analytics: period return / drawdown / volatility for an era window

No LLM here. The historical *agent* writes the beginner narrative; this
layer just produces the structured report.
"""
from app.layers.historical.analytics import compute_era_performance
from app.layers.historical.eras import ERAS, get_era
from app.layers.historical.lookup import (find_era, resolve_ticker,
                                            ticker_label_for)

__all__ = [
    "ERAS",
    "compute_era_performance",
    "find_era",
    "get_era",
    "resolve_ticker",
    "ticker_label_for",
]
