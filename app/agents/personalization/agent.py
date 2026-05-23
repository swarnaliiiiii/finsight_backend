"""Personalization agent.

Inputs (from AgentInput):
  - upstream['projection']        : Projection | None
  - upstream['projection_range']  : ProjectionRange | None
  - upstream['allocation']        : AllocationPlan | None
  - scenario                       : CurrentScenario | None
  - user                           : UserContext

Output:
  - narrative                      : plain-English framing of the numbers
  - structured                     : echoes the inputs for the Assembly agent
                                      to render as Chart/Table blocks
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.schemas import (AgentInput, AgentOutput, AllocationPlan, Projection,
                          ProjectionRange)

_DISCLAIMER = (
    "Projections use illustrative assumptions; real markets deviate. "
    "This is educational information, not financial advice.")


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly financial educator. Frame the "
     "numbers below in 4-6 sentences. ALWAYS emphasise that the range is "
     "uncertainty, not a prediction. NEVER tell the user to buy or sell. "
     "End with the exact line: 'This is educational information, not advice.'"),
    ("user",
     "User goal: {goal}\n"
     "Horizon: {horizon} years\n"
     "Currency: {currency}\n\n"
     "Point projection:\n{point}\n\n"
     "Monte Carlo range:\n{mc_range}\n\n"
     "Allocation plan:\n{allocation}\n\n"
     "Scenario context (may be empty): {scenario}\n\n"
     "Write the framing.")
])


async def run(input: AgentInput) -> AgentOutput:
    proj: Projection | None = input.upstream.get("projection")
    mc: ProjectionRange | None = input.upstream.get("projection_range")
    alloc: AllocationPlan | None = input.upstream.get("allocation")

    if proj is None and mc is None and alloc is None:
        return AgentOutput(
            narrative=("We didn't have enough numeric inputs to project a "
                        "return. Try a query like 'if I invest 5000 a month "
                        "for 10 years'."),
            disclaimer=_DISCLAIMER,
        )

    try:
        chain = _PROMPT | _llm()
        response = await chain.ainvoke({
            "goal": input.user.goal or "general wealth building",
            "horizon": input.user.horizon_years or "not specified",
            "currency": "INR" if input.user.country == "IN" else
                        "USD" if input.user.country == "US" else "GBP",
            "point": _fmt_projection(proj),
            "mc_range": _fmt_range(mc),
            "allocation": _fmt_allocation(alloc),
            "scenario": _fmt_scenario(input.scenario),
        })
        narrative = (response.content if hasattr(response, "content")
                      else str(response))
    except Exception as exc:
        narrative = _fallback_narrative(proj, mc, alloc)
        return AgentOutput(
            narrative=narrative,
            structured=_structured(proj, mc, alloc, error=str(exc)[:200]),
            disclaimer=_DISCLAIMER,
        )

    return AgentOutput(
        narrative=narrative,
        structured=_structured(proj, mc, alloc),
        disclaimer=_DISCLAIMER,
    )


def _structured(proj: Projection | None, mc: ProjectionRange | None,
                 alloc: AllocationPlan | None, error: str | None = None) -> dict:
    out: dict = {}
    if proj is not None:
        out["projection"] = proj.model_dump()
    if mc is not None:
        out["projection_range"] = mc.model_dump()
    if alloc is not None:
        out["allocation"] = alloc.model_dump()
    if error is not None:
        out["llm_error"] = error
    return out


def _fmt_projection(p: Projection | None) -> str:
    if p is None:
        return "(none)"
    return (f"  invested_total={p.invested_total}, final_value={p.final_value}, "
            f"assumed_return={p.annual_return_assumed:.2%}, "
            f"growth_multiple={p.growth_multiple}x")


def _fmt_range(r: ProjectionRange | None) -> str:
    if r is None:
        return "(none)"
    return (f"  invested={r.invested_total}, p10={r.p10}, p50={r.p50}, "
            f"p90={r.p90} (mu={r.annual_return_mean:.2%}, "
            f"sigma={r.annual_return_stdev:.2%}, n={r.n_simulations})")


def _fmt_allocation(a: AllocationPlan | None) -> str:
    if a is None:
        return "(none)"
    lines = [f"  {s.bucket}: {s.pct}% — {s.rationale}" for s in a.slices]
    return "\n".join(lines) or "(none)"


def _fmt_scenario(scenario) -> str:
    if scenario is None:
        return "(no scenario)"
    bits = []
    if scenario.policy_state and scenario.policy_state.policy_rate is not None:
        bits.append(
            f"{scenario.policy_state.authority} rate "
            f"{scenario.policy_state.policy_rate}%")
    if scenario.market_regime:
        bits.append(f"regime {scenario.market_regime.trend}")
    return "; ".join(bits) or "(quiet)"


def _fallback_narrative(proj: Projection | None, mc: ProjectionRange | None,
                         alloc: AllocationPlan | None) -> str:
    parts: list[str] = []
    if proj:
        parts.append(
            f"At the assumed {proj.annual_return_assumed:.0%} annual return, "
            f"your invested total of {proj.invested_total:,.0f} would grow to "
            f"about {proj.final_value:,.0f} ({proj.growth_multiple}x).")
    if mc:
        parts.append(
            f"Realistic range from a 1,000-run simulation: roughly "
            f"{mc.p10:,.0f} (low) to {mc.p90:,.0f} (high), with a midpoint "
            f"near {mc.p50:,.0f}.")
    if alloc:
        eq = next((s.pct for s in alloc.slices if s.bucket == "equity_sip"), None)
        if eq is not None:
            parts.append(
                f"A conventional split for your profile leans about {eq:.0f}% "
                f"to equity SIPs, with the rest spread across debt, gold, and "
                f"emergency cash.")
    parts.append("This is educational information, not advice.")
    return " ".join(parts)
