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
    # "What is a SIP?" -> KG lookup + curated resources + scenario context +
    # LLM narrative + UI pack. Resource curation uses one combined Tavily
    # call (article + video hits in one shot) — cheap and high-signal.
    Intent.EXPLAIN_TERM: [
        L("education.explain"),
        L("search.term_resources"),
        L("scenario.snapshot"),
        A("education"),
        A("assembly"),
    ],

    # "What's the repo rate today?" -> scenario snapshot already has it.
    Intent.QUICK_FACT: [
        L("scenario.snapshot"),
        A("education"),
        A("assembly"),
    ],

    # "If I invest 5000/month for 10 years..." -> point + Monte Carlo + framing.
    Intent.PROJECT_RETURNS: [
        L("projection.sip_future_value"),
        L("projection.monte_carlo"),
        L("scenario.snapshot"),
        A("personalization"),
        A("assembly"),
    ],

    # "What should I invest in?" -> allocation plan + framing.
    Intent.RECOMMEND_INSTRUMENT: [
        L("projection.allocation"),
        L("scenario.snapshot"),
        A("personalization"),
        A("assembly"),
    ],

    # "What's the latest news on X?" -> web search + scenario context +
    # scenario_policy agent for sentiment / tilts + pack.
    Intent.CURRENT_NEWS: [
        L("search.web"),
        L("scenario.snapshot"),
        A("scenario_policy"),
        A("assembly"),
    ],

    # "How did gold ETFs behave during COVID?" -> match era, fetch price
    # history, compute window stats, narrate, pack.
    Intent.HISTORICAL_BEHAVIOR: [
        L("historical.era_performance"),
        L("scenario.snapshot"),
        A("historical"),
        A("assembly"),
    ],

    # "Gold ETF vs silver ETF" / "Compare large-cap funds" ->
    # consensus + enrich + score + compare + LLM narrative + pack.
    Intent.COMPARE_INSTRUMENTS: [
        L("recommender.consensus"),
        L("recommender.enrich"),
        L("recommender.score"),
        L("recommender.compare"),
        L("scenario.snapshot"),
        A("recommendation"),
        A("assembly"),
    ],

    # Daily Brief: gather signals + LLM polish + pack.
    Intent.DAILY_BRIEF: [
        L("brief.gather"),
        L("scenario.snapshot"),
        A("brief"),
        A("assembly"),
    ],

    Intent.UNKNOWN: [A("not_implemented"), A("assembly")],
}


def plan_for(intent: Intent) -> list[PlanStep]:
    return INTENT_PLANS.get(intent, INTENT_PLANS[Intent.UNKNOWN])
