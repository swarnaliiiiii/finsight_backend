"""AgentInput / AgentOutput: the only contract that crosses the orchestrator
<-> agent boundary.

Every agent is a single async function with signature:
    async def run(input: AgentInput) -> AgentOutput

Agents see ONLY the fields the orchestrator populated. They have no other
imports from `app.layers.*` and no callable that performs I/O. If an agent
needs more data, it returns a structured `needs` list and the orchestrator
decides whether to fulfill it on a second pass.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.documents import Document
from app.schemas.intent import Intent
from app.schemas.scenario import CurrentScenario
from app.schemas.user import UserContext


class AgentInput(BaseModel, frozen=True):
    """Read-only bundle passed to an agent's `run` function."""
    query: str
    intent: Intent
    user: UserContext
    scenario: CurrentScenario | None = None
    documents: list[Document] = Field(default_factory=list)
    market_data: dict[str, Any] = Field(default_factory=dict)
    history: dict[str, Any] = Field(default_factory=dict)
    upstream: dict[str, Any] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel, frozen=True):
    """What every agent returns. The orchestrator merges these into the final
    response via the Assembly agent."""
    narrative: str | None = None
    structured: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
