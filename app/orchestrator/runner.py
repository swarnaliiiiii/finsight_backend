"""Orchestrator entry-point: free-form query in, AgentOutput out.

Flow:
  1. Classify intent via Intent agent.
  2. Look up the deterministic plan for that intent.
  3. Execute each step in order:
       - 'layer' step  -> call whitelisted function from LAYER_CALLS
       - 'agent' step  -> build AgentInput from accumulator, invoke agent
  4. Return the final agent's AgentOutput, with budget + intent merged into
     `structured` so the API can surface them.

Architectural invariants enforced here:
  - Agents are dispatched ONLY through this runner (the AGENT_REGISTRY)
  - Agents receive a fresh frozen AgentInput per invocation
  - No agent calls another agent or any layer directly
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.agents import education as education_agent
from app.agents import intent as intent_agent
from app.agents import not_implemented as not_implemented_agent
from app.orchestrator.budget import BudgetExceeded, QueryBudget
from app.orchestrator.layer_calls import LAYER_CALLS, RunContext
from app.orchestrator.planner import PlanStep, plan_for
from app.schemas import AgentInput, AgentOutput, Intent, UserContext

logger = logging.getLogger(__name__)


AgentRun = Callable[[AgentInput], Awaitable[AgentOutput]]

# The orchestrator's view of the agent universe. Plans reference these names.
AGENT_REGISTRY: dict[str, AgentRun] = {
    "intent": intent_agent.run,
    "education": education_agent.run,
    "not_implemented": not_implemented_agent.run,
}


async def ask(query: str, user: UserContext,
               budget: QueryBudget | None = None) -> AgentOutput:
    """Top-level orchestrator call."""
    budget = budget or QueryBudget()
    ctx = RunContext(query=query, user=user, budget=budget)

    intent = await _classify(ctx)
    ctx.stash("intent", intent)

    steps = plan_for(intent)
    final: AgentOutput | None = None
    try:
        for step in steps:
            final = await _run_step(step, ctx, intent)
    except BudgetExceeded as exc:
        ctx.budget.note(str(exc))
        if final is None:
            final = AgentOutput(
                narrative="Sorry, this query exceeded its compute budget before "
                          "we could finish. Try a simpler question.",
                structured={"intent": intent.value, "error": str(exc)},
            )

    assert final is not None  # every plan ends with at least one agent step
    merged_structured = dict(final.structured)
    merged_structured.setdefault("intent", intent.value)
    merged_structured["budget"] = ctx.budget.as_dict()
    return final.model_copy(update={"structured": merged_structured})


# --- internals -------------------------------------------------------------

async def _classify(ctx: RunContext) -> Intent:
    """Run the intent agent and pull the classified Intent out of its output."""
    ctx.budget.spend_agent_invocation("intent")
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
    return await runner(agent_input)


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
