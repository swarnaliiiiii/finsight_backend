"""Bridge: enrich a freshly built scenario snapshot with LLM-graded tilts.

This module is the architectural cleanroom for the one place where the
Scenario layer and the Scenario-Policy agent meet. Layers cannot import
agents; agents cannot import layers. The orchestrator is the only module
allowed to import both.

The refresher loop calls this via a callback, so the layer code stays
agent-free. If the callback fails or the agent has no LLM key, we return
the snapshot unchanged (with `instrument_tilts={}`) — every downstream
agent already handles that.
"""
from __future__ import annotations

import logging

from app.agents.scenario_policy import run as scenario_policy_run
from app.schemas import AgentInput, CurrentScenario, Intent, UserContext

logger = logging.getLogger(__name__)


async def enrich_scenario_with_tilts(snapshot: CurrentScenario
                                       ) -> CurrentScenario:
    """Invoke the scenario_policy agent with a synthetic AgentInput and
    return an updated snapshot whose `instrument_tilts` is populated."""
    agent_input = AgentInput(
        query="",
        intent=Intent.UNKNOWN,
        user=UserContext(country=snapshot.country),
        scenario=snapshot,
    )
    try:
        out = await scenario_policy_run(agent_input)
    except Exception:
        logger.exception("scenario_policy enrich failed; keeping empty tilts")
        return snapshot
    tilts = out.structured.get("tilts") if out.structured else None
    if not isinstance(tilts, dict) or not tilts:
        return snapshot
    return snapshot.model_copy(update={"instrument_tilts": dict(tilts)})
