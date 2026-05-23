"""Education agent.

Inputs (from AgentInput):
  - upstream["explanation"] : Explanation | None (from education layer)
  - scenario               : CurrentScenario | None
  - query                  : user's original NL question

Output:
  - narrative              : 4-6 sentences, beginner tone
  - structured             : echoes the Explanation + key live values
  - citations              : data_source ids from affecting entities

If the layer returned `None` (term not in KG), we degrade to a polite
"that term isn't in our glossary yet" response — the agent still returns
cleanly so the orchestrator doesn't have to special-case missing data.
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.schemas import AgentInput, AgentOutput, Explanation

_DISCLAIMER = (
    "This is educational information based on public data, not financial advice."
)


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly financial educator. Write 4-6 "
     "sentences in plain English that a first-time investor understands. "
     "NEVER tell the user to buy or sell. Always end with the exact line: "
     "'This is educational information, not advice.'"),
    ("user",
     "User asked: {query}\n\n"
     "Term: {term}\n"
     "Plain-English definition: {plain_english}\n"
     "Why it matters: {why_it_matters}\n"
     "Things that affect it (with live values where available):\n"
     "{entities}\n\n"
     "Current scenario context (may be empty): {scenario_note}\n\n"
     "Compose the explanation. Weave in one or two of the live values where "
     "it helps the reader. If the scenario context has anything relevant, "
     "mention it briefly; otherwise ignore it.")
])


def _entities_lines(explanation: Explanation) -> str:
    lines: list[str] = []
    for e in explanation.affecting_entities:
        live = f" (current: {e.current_value})" if e.current_value else ""
        lines.append(f"- {e.name}{live} — {e.description}")
    return "\n".join(lines) or "(none recorded)"


def _scenario_note(scenario) -> str:
    if scenario is None:
        return "(no scenario data available)"
    parts = []
    if scenario.policy_state and scenario.policy_state.policy_rate is not None:
        parts.append(
            f"{scenario.policy_state.authority} policy rate "
            f"{scenario.policy_state.policy_rate}%")
    if scenario.market_regime:
        parts.append(f"market regime {scenario.market_regime.trend}/"
                      f"{scenario.market_regime.volatility_band}")
    if scenario.active_events:
        top = scenario.active_events[0]
        parts.append(f"active event: {top.type.value} — {top.headline}")
    return "; ".join(parts) or "(quiet)"


async def run(input: AgentInput) -> AgentOutput:
    explanation: Explanation | None = input.upstream.get("explanation")

    if explanation is None:
        return AgentOutput(
            narrative=(
                "That term isn't in our beginner glossary yet — try a core "
                "concept like SIP, ETF, mutual fund, bond, NCD, FD, or stock. "
                "This is educational information, not advice."),
            structured={"term": input.upstream.get("term")},
            disclaimer=_DISCLAIMER,
        )

    citations = [e.data_source for e in explanation.affecting_entities
                  if e.data_source]

    try:
        chain = _PROMPT | _llm()
        response = await chain.ainvoke({
            "query": input.query,
            "term": explanation.term,
            "plain_english": explanation.plain_english,
            "why_it_matters": explanation.why_it_matters,
            "entities": _entities_lines(explanation),
            "scenario_note": _scenario_note(input.scenario),
        })
        narrative = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        # Graceful degradation: serve the KG content directly with no LLM polish.
        narrative = (
            f"{explanation.plain_english} {explanation.why_it_matters} "
            "This is educational information, not advice.")
        return AgentOutput(
            narrative=narrative,
            structured={"term": explanation.term,
                         "explanation": explanation.model_dump(),
                         "llm_error": str(exc)[:200]},
            citations=citations,
            disclaimer=_DISCLAIMER,
        )

    return AgentOutput(
        narrative=narrative,
        structured={"term": explanation.term,
                     "explanation": explanation.model_dump()},
        citations=citations,
        disclaimer=_DISCLAIMER,
    )
