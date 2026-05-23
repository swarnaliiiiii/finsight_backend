"""Shared frozen data contracts.

This package defines the *only* types that may cross the orchestrator <-> agent
boundary. Agents receive an `AgentInput` and return an `AgentOutput`; nothing
else. Layers produce typed values (`CurrentScenario`, `Document`, ...) that the
orchestrator places into `AgentInput` before invoking an agent.

Rules enforced architecturally (see .importlinter at repo root):
  - `app.agents.*` may import from `app.schemas.*`
  - `app.agents.*` may NOT import from `app.layers.*`
  - `app.agents.*` may NOT import from other agents
"""
from app.schemas.agent_io import AgentInput, AgentOutput
from app.schemas.brief import (BriefItem, BriefSeverity, BriefSourceType,
                                 DailyBrief)
from app.schemas.documents import Document
from app.schemas.instruments import (AffectingEntity, Comparison, Explanation,
                                       InstrumentCandidate, Recommendation)
from app.schemas.intent import Intent
from app.schemas.scenario import (CurrentScenario, Event, EventType,
                                    MarketRegime, PolicyState)
from app.schemas.user import InstrumentType, RiskLevel, UserContext

__all__ = [
    "AffectingEntity",
    "AgentInput",
    "AgentOutput",
    "BriefItem",
    "BriefSeverity",
    "BriefSourceType",
    "Comparison",
    "CurrentScenario",
    "DailyBrief",
    "Document",
    "Event",
    "EventType",
    "Explanation",
    "InstrumentCandidate",
    "InstrumentType",
    "Intent",
    "MarketRegime",
    "PolicyState",
    "Recommendation",
    "RiskLevel",
    "UserContext",
]
