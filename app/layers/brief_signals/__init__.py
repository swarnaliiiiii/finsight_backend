"""Brief signals layer: market-pulse, macro-movement, and trending-news
gatherers used by the Daily Brief flow. Pure I/O + structuring; no LLM."""
from app.layers.brief_signals.signals import (Signal, macro_movements,
                                                 market_pulse, trending_news)

__all__ = ["Signal", "macro_movements", "market_pulse", "trending_news"]
