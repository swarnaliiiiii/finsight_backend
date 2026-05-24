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
from app.schemas.assembly import (Block, CalloutBlock, ChartBlock,
                                     CitationsBlock, FormBlock, ListBlock,
                                     NarrativeBlock, ResponseEnvelope,
                                     TableBlock, VideoBlock)
from app.schemas.brief import (BriefItem, BriefSeverity, BriefSourceType,
                                 DailyBrief, Signal)
from app.schemas.documents import Document
from app.schemas.historical import Era, EraPerformance, HistoricalReport
from app.schemas.instruments import (AffectingEntity, Comparison, Explanation,
                                       InstrumentCandidate, Recommendation)
from app.schemas.intent import Intent
from app.schemas.memory import (MemoryActivity, MemoryProfile, MemoryReadout,
                                   MemorySessionTurn)
from app.schemas.projection import (AllocationPlan, AllocationSlice,
                                       Projection, ProjectionRange)
from app.schemas.scenario import (CurrentScenario, Event, EventType,
                                    MarketRegime, PolicyState)
from app.schemas.user import InstrumentType, RiskLevel, UserContext

__all__ = [
    "AffectingEntity",
    "AgentInput",
    "AgentOutput",
    "AllocationPlan",
    "AllocationSlice",
    "Block",
    "BriefItem",
    "BriefSeverity",
    "BriefSourceType",
    "CalloutBlock",
    "ChartBlock",
    "CitationsBlock",
    "Comparison",
    "CurrentScenario",
    "DailyBrief",
    "Document",
    "Era",
    "EraPerformance",
    "Event",
    "EventType",
    "Explanation",
    "FormBlock",
    "HistoricalReport",
    "InstrumentCandidate",
    "InstrumentType",
    "Intent",
    "ListBlock",
    "MarketRegime",
    "MemoryActivity",
    "MemoryProfile",
    "MemoryReadout",
    "MemorySessionTurn",
    "NarrativeBlock",
    "PolicyState",
    "Projection",
    "ProjectionRange",
    "Recommendation",
    "ResponseEnvelope",
    "RiskLevel",
    "Signal",
    "TableBlock",
    "UserContext",
    "VideoBlock",
]
