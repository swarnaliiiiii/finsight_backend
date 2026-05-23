"""Deterministic Intent -> plan registry.

A plan is a list of steps; each step is either a layer call (string name into
`LAYER_CALLS`) or an agent invocation (string name into `AGENT_REGISTRY`).
The runner executes the steps in order.

Adding a new intent = add an enum value (in `app.schemas.Intent`), add a plan
here, and (if needed) register new layer-calls or agents. No runner changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas import Intent

StepKind = Literal["layer", "agent"]


@dataclass(frozen=True)
class PlanStep:
    kind: StepKind
    name: str


# Helper aliases for readability below.
def L(name: str) -> PlanStep: return PlanStep("layer", name)
def A(name: str) -> PlanStep: return PlanStep("agent", name)


INTENT_PLANS: dict[Intent, list[PlanStep]] = {
    # "What is a SIP?" -> KG lookup + scenario context + LLM narrative.
    Intent.EXPLAIN_TERM: [
        L("education.explain"),
        L("scenario.snapshot"),
        A("education"),
    ],

    # "What's the repo rate today?" -> scenario snapshot already has it.
    Intent.QUICK_FACT: [
        L("scenario.snapshot"),
        A("education"),
    ],

    # The rest are stubs for now — they classify cleanly but the plans
    # return a "not yet wired" message via the placeholder agent. This keeps
    # the orchestrator complete and lets later steps add capability by
    # filling in agents/layer-calls, not by editing the runner.
    Intent.COMPARE_INSTRUMENTS: [A("not_implemented")],
    Intent.RECOMMEND_INSTRUMENT: [A("not_implemented")],
    Intent.PROJECT_RETURNS: [A("not_implemented")],
    Intent.CURRENT_NEWS: [A("not_implemented")],
    Intent.HISTORICAL_BEHAVIOR: [A("not_implemented")],
    Intent.DAILY_BRIEF: [A("not_implemented")],
    Intent.UNKNOWN: [A("not_implemented")],
}


def plan_for(intent: Intent) -> list[PlanStep]:
    return INTENT_PLANS.get(intent, INTENT_PLANS[Intent.UNKNOWN])
