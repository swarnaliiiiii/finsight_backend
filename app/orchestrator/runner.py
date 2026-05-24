"""Orchestrator entry-point: free-form query in, ResponseEnvelope out.

Flow:
  1. Classify intent via Intent agent.
  2. Look up the deterministic plan for that intent.
  3. Execute each step in order:
       - 'layer' step  -> call whitelisted function from LAYER_CALLS
       - 'agent' step  -> build AgentInput from accumulator, invoke agent,
                          stash its AgentOutput under
                          accumulator['__agent_outputs__'][name]
  4. If the plan included an Assembly agent, return its envelope.
     Otherwise, wrap the last agent's narrative in a default envelope.

Architectural invariants enforced here:
  - Agents are dispatched ONLY through this runner (the AGENT_REGISTRY)
  - Agents receive a fresh frozen AgentInput per invocation
  - No agent calls another agent or any layer directly
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.agents import assembly as assembly_agent
from app.agents import brief as brief_agent
from app.agents import education as education_agent
from app.agents import historical as historical_agent
from app.agents import instrument_starter as instrument_starter_agent
from app.agents import intent as intent_agent
from app.agents import not_implemented as not_implemented_agent
from app.agents import personalization as personalization_agent
from app.agents import recommendation as recommendation_agent
from app.agents import scenario_policy as scenario_policy_agent
from app.orchestrator.budget import BudgetExceeded, QueryBudget
from app.orchestrator.layer_calls import LAYER_CALLS, RunContext
from app.orchestrator.planner import PlanStep, plan_for
from app.schemas import (AgentInput, AgentOutput, Intent, NarrativeBlock,
                          ResponseEnvelope, UserContext)

logger = logging.getLogger(__name__)


AgentRun = Callable[[AgentInput], Awaitable[AgentOutput]]

# The orchestrator's view of the agent universe. Plans reference these names.
AGENT_REGISTRY: dict[str, AgentRun] = {
    "intent": intent_agent.run,
    "education": education_agent.run,
    "personalization": personalization_agent.run,
    "recommendation": recommendation_agent.run,
    "historical": historical_agent.run,
    "scenario_policy": scenario_policy_agent.run,
    "brief": brief_agent.run,
    "instrument_starter": instrument_starter_agent.run,
    "not_implemented": not_implemented_agent.run,
    "assembly": assembly_agent.run,
}

_AGENT_OUTPUTS_KEY = "__agent_outputs__"


async def ask(query: str, user: UserContext,
               budget: QueryBudget | None = None,
               user_id: str | None = None,
               session_id: str | None = None) -> ResponseEnvelope:
    """Top-level orchestrator call. Returns a ResponseEnvelope ready for the UI.

    `user_id` / `session_id` are opaque identifiers from the HTTP layer. If
    present, the orchestrator hydrates UserContext from the memory layer
    before classifying intent, and persists this turn at the end.
    """
    budget = budget or QueryBudget()
    ctx = RunContext(query=query, user=user, budget=budget,
                      user_id=user_id, session_id=session_id)
    ctx.accumulator[_AGENT_OUTPUTS_KEY] = {}

    # Memory readout runs BEFORE intent classification so the Context half
    # of the Intent agent can see the persisted profile + recent turns.
    if user_id:
        try:
            await _run_layer_step("memory.readout", ctx)
        except BudgetExceeded as exc:
            ctx.budget.note(str(exc))

    intent = await _classify(ctx)
    ctx.stash("intent", intent)

    steps = plan_for(intent)
    last_output: AgentOutput | None = None
    try:
        for step in steps:
            step_output = await _run_step(step, ctx, intent)
            if step_output is not None:
                last_output = step_output
    except BudgetExceeded as exc:
        ctx.budget.note(str(exc))

    envelope = _final_envelope(ctx, intent, query, last_output)

    # Persist the turn + activity AFTER the envelope is built, so the
    # persisted JSONB matches what the user actually saw. Best-effort.
    if user_id:
        try:
            await LAYER_CALLS["memory.record_turn"](ctx)
            await LAYER_CALLS["memory.record_activity"](ctx)
        except Exception:
            logger.exception("memory persistence failed user=%s", user_id)

    debug = dict(envelope.debug)
    debug["budget"] = ctx.budget.as_dict()
    return envelope.model_copy(update={"debug": debug})


# --- internals -------------------------------------------------------------

async def _classify(ctx: RunContext) -> Intent:
    """Run the intent agent and pull the classified Intent out of its output."""
    try:
        ctx.budget.spend_agent_invocation("intent")
    except BudgetExceeded:
        return Intent.UNKNOWN
    agent_input = _build_agent_input(ctx, intent=Intent.UNKNOWN)
    out = await intent_agent.run(agent_input)
    raw = out.structured.get("intent")
    try:
        return Intent(raw) if raw else Intent.UNKNOWN
    except ValueError:
        logger.warning("intent agent returned unknown value: %r", raw)
        return Intent.UNKNOWN


async def _run_step(step: PlanStep, ctx: RunContext, intent: Intent
                      ) -> AgentOutput | None:
    if step.kind == "layer":
        return await _run_layer_step(step.name, ctx)
    if step.kind == "agent":
        return await _run_agent_step(step.name, ctx, intent)
    raise ValueError(f"unknown plan step kind: {step.kind!r}")


async def _run_layer_step(name: str, ctx: RunContext) -> None:
    call = LAYER_CALLS.get(name)
    if call is None:
        raise KeyError(f"unknown layer call: {name!r}")
    ctx.budget.spend_layer_call(name)
    await call(ctx)
    return None


async def _run_agent_step(name: str, ctx: RunContext,
                            intent: Intent) -> AgentOutput:
    runner = AGENT_REGISTRY.get(name)
    if runner is None:
        raise KeyError(f"unknown agent: {name!r}")
    ctx.budget.spend_agent_invocation(name)
    agent_input = _build_agent_input(ctx, intent=intent)
    out = await runner(agent_input)
    ctx.accumulator[_AGENT_OUTPUTS_KEY][name] = out
    return out


def _build_agent_input(ctx: RunContext, intent: Intent) -> AgentInput:
    """Snapshot the accumulator into a frozen AgentInput for an agent call.

    The agent sees only what the orchestrator chose to pass. The accumulator
    itself never leaves this module.
    """
    acc = ctx.accumulator
    return AgentInput(
        query=ctx.query,
        intent=intent,
        user=ctx.user,
        scenario=acc.get("scenario"),
        documents=acc.get("documents", []),
        market_data=acc.get("market_data", {}),
        history=acc.get("history", {}),
        upstream={k: v for k, v in acc.items()
                   if k not in {"scenario", "documents", "market_data",
                                 "history", "intent"}},
    )


def _final_envelope(ctx: RunContext, intent: Intent, query: str,
                      last_output: AgentOutput | None) -> ResponseEnvelope:
    """Extract the envelope from the Assembly agent's output, or build a
    minimal one from the last agent's narrative."""
    assembly_out = ctx.accumulator.get(_AGENT_OUTPUTS_KEY, {}).get("assembly")
    if assembly_out is not None:
        env_dict = assembly_out.structured.get("envelope")
        if isinstance(env_dict, dict):
            try:
                return ResponseEnvelope.model_validate(env_dict)
            except Exception:
                logger.exception("assembly envelope failed validation; falling back")
    # Fallback: wrap whatever the last agent said in a single narrative block.
    text = (last_output.narrative if last_output and last_output.narrative
             else "Sorry — no response was produced for this query.")
    return ResponseEnvelope(
        intent=intent,
        query=query,
        blocks=[NarrativeBlock(text=text)],
    )
