"""Placeholder agent for intents whose plans haven't been wired yet.

Returns a polite, structured "not yet supported" response so the orchestrator
contract holds end-to-end while we build the remaining capabilities.
"""
from app.agents.not_implemented.agent import run

__all__ = ["run"]
