"""Recommendation Reasoning agent.

Beginner-safe narrative on top of the deterministic Recommender layer's
ranked candidates. Scenario-aware. Never prescriptive.
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.core.geography import market_locale
from app.schemas import (AgentInput, AgentOutput, Comparison, CurrentScenario,
                          InstrumentCandidate)

_DISCLAIMER = (
    "This is educational information based on public data, not financial advice. "
    "Past performance does not guarantee future returns.")


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.2,
    )


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly financial educator. You NEVER "
     "tell users to buy or sell. You explain the candidates in plain English "
     "so a first-time investor can decide. Always end with the exact line: "
     "'This is educational information, not advice.'"),
    ("user",
     "User context:\n"
     "- Country: {country} (market: {market}, currency: {currency})\n"
     "- Instrument: {instrument}\n"
     "- Amount: {amount}\n"
     "- Horizon (years): {horizon}\n"
     "- Risk tolerance: {risk}\n"
     "- Goal: {goal}\n\n"
     "Top candidates (already ranked by our scoring):\n{candidates}\n\n"
     "Backdrop (may be empty): {scenario}\n\n"
     "Write a 4-6 sentence explanation: which one stands out and why, what "
     "beginners on local platforms (Groww/Zerodha in India, Vanguard/Fidelity "
     "in US) typically prefer, and one risk they should know. Reference the "
     "backdrop briefly if relevant; ignore it otherwise.")
])


async def run(input: AgentInput) -> AgentOutput:
    candidates: list[InstrumentCandidate] = input.upstream.get("candidates") or []
    comparison: Comparison | None = input.upstream.get("comparison")
    user = input.user

    if not candidates:
        return AgentOutput(
            narrative=("We couldn't fetch ranked candidates for this query. "
                        "Try a more specific instrument hint, e.g. 'best "
                        "large-cap SIP funds'. "
                        "This is educational information, not advice."),
            disclaimer=_DISCLAIMER,
        )

    top = candidates[0]
    locale = market_locale(user.country)  # type: ignore[arg-type]
    candidate_lines = "\n".join(
        f"- {c.name} (provider: {c.provider or 'n/a'}, "
        f"category: {c.category or 'n/a'}, "
        f"risk: {c.risk_level.value if c.risk_level else 'n/a'}, "
        f"consensus_rank: {c.consensus_rank or 'n/a'})"
        for c in candidates[:5]
    ) or "(no candidates found)"

    try:
        chain = _PROMPT | _llm()
        response = await chain.ainvoke({
            "country": user.country,
            "market": locale["primary_index"],
            "currency": locale["currency"],
            "instrument": (user.instrument_type.value
                            if user.instrument_type else "not specified"),
            "amount": user.amount or "not specified",
            "horizon": user.horizon_years or "not specified",
            "risk": (user.risk_tolerance.value
                      if user.risk_tolerance else "not specified"),
            "goal": user.goal or "general wealth building",
            "candidates": candidate_lines,
            "scenario": _fmt_scenario(input.scenario),
        })
        narrative = (response.content if hasattr(response, "content")
                      else str(response))
    except Exception as exc:
        narrative = _fallback_narrative(top, candidates)
        return AgentOutput(
            narrative=narrative,
            structured=_structured(candidates, comparison, top, error=str(exc)[:200]),
            disclaimer=_DISCLAIMER,
        )

    return AgentOutput(
        narrative=narrative,
        structured=_structured(candidates, comparison, top),
        disclaimer=_DISCLAIMER,
    )


def _structured(candidates: list[InstrumentCandidate],
                 comparison: Comparison | None,
                 top: InstrumentCandidate,
                 error: str | None = None) -> dict:
    out: dict = {
        "candidates": [c.model_dump() for c in candidates],
        "top_pick_id": top.id,
        "consensus_summary": _consensus_summary(candidates),
    }
    if comparison is not None:
        out["comparison"] = comparison.model_dump()
    if error is not None:
        out["llm_error"] = error
    return out


def _consensus_summary(candidates: list[InstrumentCandidate]) -> str:
    if not candidates:
        return "No consensus data available for this query."
    sources: set[str] = set()
    for c in candidates:
        sources.update(c.consensus_sources)
    src_label = ", ".join(sorted(sources)) or "public sources"
    return (f"Drawn from {src_label}. Top of the consensus list: "
            f"{candidates[0].name}.")


def _fmt_scenario(scenario: CurrentScenario | None) -> str:
    if scenario is None:
        return "(no scenario)"
    bits = []
    if scenario.policy_state and scenario.policy_state.policy_rate is not None:
        bits.append(f"{scenario.policy_state.authority} rate "
                     f"{scenario.policy_state.policy_rate}%")
    if scenario.market_regime:
        bits.append(f"regime {scenario.market_regime.trend}")
    if scenario.active_events:
        bits.append(f"active: {scenario.active_events[0].type.value}")
    return "; ".join(bits) or "(quiet)"


def _fallback_narrative(top: InstrumentCandidate,
                          candidates: list[InstrumentCandidate]) -> str:
    return (f"Among {len(candidates)} ranked candidates, {top.name} sits at "
            f"the top by our scoring (returns + expense ratio + consensus "
            f"rank). Beginners typically also consider 1-2 of the next "
            f"options to diversify. "
            "This is educational information, not advice.")
