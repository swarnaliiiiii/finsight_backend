"""Personalization agent: frames projection / allocation numbers for the user.

Reads `input.upstream` for `projection`, `projection_range`, and
`allocation` payloads stashed by the orchestrator. Returns a beginner-safe
narrative explaining the range and trade-offs. Never prescriptive.
"""
from app.agents.personalization.agent import run

__all__ = ["run"]
