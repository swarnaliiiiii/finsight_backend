"""Whitelisted layer-call wrappers.

Plan steps reference layer calls by NAME (string). The runner looks the name
up in `LAYER_CALLS` here. This is the only place where layers are reached
from the orchestrator side — agents never see these functions because they
can't import this module (it lives under orchestrator/).

Each wrapper:
  - takes (ctx: RunContext) -> writes results into ctx.accumulator
  - is cheap to add: new capability == one new function + one registry entry
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.layers.education import explain as education_explain
from app.layers.scenario import scenario_store
from app.orchestrator.budget import QueryBudget
from app.schemas import UserContext


@dataclass
class RunContext:
    """Mutable bundle threaded through plan execution. The orchestrator owns
    this — agents never see it (they receive a frozen AgentInput built from
    its accumulator)."""
    query: str
    user: UserContext
    budget: QueryBudget
    accumulator: dict[str, Any] = field(default_factory=dict)

    def stash(self, key: str, value: Any) -> None:
        self.accumulator[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.accumulator.get(key, default)


# --- layer-call implementations -------------------------------------------

async def _call_scenario_snapshot(ctx: RunContext) -> None:
    snap = scenario_store.get(ctx.user.country)
    ctx.stash("scenario", snap)


async def _call_education_explain(ctx: RunContext) -> None:
    """Look up the term the user is asking about and stash the layer's
    structured Explanation (or None if the term isn't in the KG)."""
    term = ctx.get("term") or _guess_term(ctx.query)
    if not term:
        ctx.stash("explanation", None)
        return
    result = await education_explain(term, country=ctx.user.country)
    ctx.stash("term", term)
    ctx.stash("explanation", result)


def _guess_term(query: str) -> str | None:
    """Cheap term extractor for queries like 'what is sip', 'explain etf'."""
    q = query.lower().strip()
    for prefix in ("what is a ", "what is an ", "what is ", "what's a ",
                    "what's an ", "what's ", "explain ", "tell me about ",
                    "how does ", "how do ", "how to start a ", "how to start "):
        if q.startswith(prefix):
            tail = q[len(prefix):].strip(" ?.")
            tail = tail.split(" ")[0]  # first word — works for short FAQs
            return tail
    return None


# --- registry --------------------------------------------------------------

LayerCall = Callable[[RunContext], Awaitable[None]]

LAYER_CALLS: dict[str, LayerCall] = {
    "scenario.snapshot": _call_scenario_snapshot,
    "education.explain": _call_education_explain,
}
