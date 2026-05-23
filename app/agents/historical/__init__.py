"""Historical Behavior agent: narrates an EraPerformance report.

Reads `input.upstream['historical_report']` (a HistoricalReport stashed by
the orchestrator) and produces a 4-6 sentence beginner-safe framing of how
the instrument behaved during the era. Never prescriptive.
"""
from app.agents.historical.agent import run

__all__ = ["run"]
