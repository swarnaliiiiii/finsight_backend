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

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.layers.education import explain as education_explain
from app.layers.projection import (allocation_for_profile, monte_carlo_sip,
                                      sip_future_value)
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


# --- projection layer-calls ------------------------------------------------

_DEFAULT_ASSUMED_RETURN = 0.12  # illustrative; the agent flags this as an assumption


async def _call_projection_sip_fv(ctx: RunContext) -> None:
    """Deterministic SIP future value. Pulls monthly + years from either the
    UserContext or by parsing them out of the free-form query."""
    monthly, years = _resolve_amount_and_horizon(ctx)
    if monthly is None or years is None:
        ctx.stash("projection", None)
        return
    ctx.stash("projection",
               sip_future_value(monthly, _DEFAULT_ASSUMED_RETURN, years))


async def _call_projection_monte_carlo(ctx: RunContext) -> None:
    """Monte Carlo range for an SIP. Same inputs as projection.sip_fv."""
    monthly, years = _resolve_amount_and_horizon(ctx)
    if monthly is None or years is None:
        ctx.stash("projection_range", None)
        return
    ctx.stash("projection_range",
               monte_carlo_sip(monthly, years, seed=1234))


async def _call_projection_allocation(ctx: RunContext) -> None:
    """Rule-based allocation for the user's profile."""
    plan = allocation_for_profile(
        age=ctx.user.age,
        risk=ctx.user.risk_tolerance,
        target_monthly=ctx.user.amount,
    )
    ctx.stash("allocation", plan)


# --- input parsers ---------------------------------------------------------

_AMOUNT_RE = re.compile(
    r"(?:invest|put|save)\s+(?:rs\.?|₹|\$|£)?\s?([\d,]+(?:\.\d+)?)"
    r"(?:\s?(k|lakh|crore|cr|l))?", re.I)
_HORIZON_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:year|yr|y)s?\b", re.I)
_SCALE = {"k": 1_000, "l": 100_000, "lakh": 100_000, "cr": 10_000_000,
           "crore": 10_000_000}


def _resolve_amount_and_horizon(ctx: RunContext) -> tuple[float | None,
                                                              float | None]:
    """Use UserContext fields first; fall back to parsing the NL query."""
    monthly = ctx.user.amount
    years: float | None = (float(ctx.user.horizon_years)
                            if ctx.user.horizon_years is not None else None)
    if monthly is None:
        m = _AMOUNT_RE.search(ctx.query)
        if m:
            try:
                amt = float(m.group(1).replace(",", ""))
                scale = (_SCALE.get(m.group(2).lower(), 1)
                          if m.group(2) else 1)
                monthly = amt * scale
            except (ValueError, AttributeError):
                pass
    if years is None:
        m = _HORIZON_RE.search(ctx.query)
        if m:
            try:
                years = float(m.group(1))
            except ValueError:
                pass
    return monthly, years


# --- registry --------------------------------------------------------------

LayerCall = Callable[[RunContext], Awaitable[None]]

LAYER_CALLS: dict[str, LayerCall] = {
    "scenario.snapshot": _call_scenario_snapshot,
    "education.explain": _call_education_explain,
    "projection.sip_future_value": _call_projection_sip_fv,
    "projection.monte_carlo": _call_projection_monte_carlo,
    "projection.allocation": _call_projection_allocation,
}
