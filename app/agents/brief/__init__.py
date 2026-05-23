"""Daily Brief agent: turn gathered signals into 3 plain-English action items
plus a one-line market summary.

Refactored from the legacy `app/brief/agent.py` LangGraph workflow — the
gather step now lives as a layer-call, and this agent only handles the
ranking, polishing, and summarising (the LLM-driven part).
"""
from app.agents.brief.agent import run

__all__ = ["run"]
