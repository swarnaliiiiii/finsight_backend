"""Response Assembly agent: packages plan outputs into a typed UI envelope.

Deterministic v1 — no LLM. Walks the upstream agent outputs, emits typed
blocks (narrative, table, list, citations, ...), wraps them in a
`ResponseEnvelope`, and returns it inside `AgentOutput.structured['envelope']`.
The orchestrator runner unwraps that and ships it as the HTTP response.
"""
from app.agents.assembly.agent import run

__all__ = ["run"]
