"""Advisor Agent: LangGraph workflow that takes UserContext and returns a
Recommendation with educational + suggestive output (never prescriptive).

Single agent, geography + instrument routing handled inside via state.
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from app.layers.education import explain
from app.layers.recommender import consensus_fetcher, enrich, score_candidates
from app.schemas import (Explanation, InstrumentCandidate, Recommendation,
                          UserContext)
from app.config import settings
from app.core.geography import market_locale


class AgentState(TypedDict, total=False):
    user: UserContext
    candidates: list[InstrumentCandidate]
    explanation: Explanation | None
    reasoning: str
    top_pick_id: str | None
    consensus_summary: str | None


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.2,
    )


# --- Nodes ----------------------------------------------------------------------


async def node_fetch_consensus(state: AgentState) -> AgentState:
    user = state["user"]
    candidates = await consensus_fetcher.fetch(
        instrument_type=user.instrument_type,
        country=user.country,
        category=user.goal,
    )
    return {"candidates": candidates[:8]}


async def node_enrich(state: AgentState) -> AgentState:
    user = state["user"]
    enriched = await enrich(state.get("candidates", []), user.country)
    return {"candidates": enriched}


async def node_score(state: AgentState) -> AgentState:
    user = state["user"]
    ranked = score_candidates(state.get("candidates", []), user)
    top_id = ranked[0].id if ranked else None
    return {"candidates": ranked, "top_pick_id": top_id}


async def node_explain(state: AgentState) -> AgentState:
    user = state["user"]
    ex = await explain(user.instrument_type.value, country=user.country)
    return {"explanation": ex}


async def node_reason(state: AgentState) -> AgentState:
    user = state["user"]
    candidates = state.get("candidates", [])[:5]
    locale = market_locale(user.country)  # type: ignore[arg-type]
    candidate_lines = [
        f"- {c.name} (provider: {c.provider or 'n/a'}, "
        f"category: {c.category or 'n/a'}, "
        f"risk: {c.risk_level.value if c.risk_level else 'n/a'}, "
        f"consensus_rank: {c.consensus_rank or 'n/a'})"
        for c in candidates
    ]
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are FinSight, a beginner-friendly financial educator. You NEVER tell users to buy "
         "or sell. You explain the candidates in plain English so a first-time investor "
         "can decide. Always end with the line: 'This is educational information, not advice.'"),
        ("user",
         "User context:\n"
         "- Country: {country} (market: {market}, currency: {currency})\n"
         "- Instrument: {instrument}\n"
         "- Amount: {amount}\n"
         "- Horizon (years): {horizon}\n"
         "- Risk tolerance: {risk}\n"
         "- Goal: {goal}\n\n"
         "Top candidates (already ranked by our scoring):\n{candidates}\n\n"
         "Write a 4-6 sentence explanation in plain English: which one stands out and why, "
         "what beginners on local platforms (Groww/Zerodha in India, Vanguard/Fidelity in US) "
         "typically prefer, and one risk they should know.")
    ])
    chain = prompt | _llm()
    response = await chain.ainvoke({
        "country": user.country,
        "market": locale["primary_index"],
        "currency": locale["currency"],
        "instrument": user.instrument_type.value,
        "amount": user.amount or "not specified",
        "horizon": user.horizon_years or "not specified",
        "risk": user.risk_tolerance.value if user.risk_tolerance else "not specified",
        "goal": user.goal or "general wealth building",
        "candidates": "\n".join(candidate_lines) or "(no candidates found)",
    })
    reasoning = response.content if hasattr(response, "content") else str(response)
    consensus_summary = _build_consensus_summary(candidates)
    return {"reasoning": reasoning, "consensus_summary": consensus_summary}


def _build_consensus_summary(candidates: list[InstrumentCandidate]) -> str:
    if not candidates:
        return "No consensus data available for this query."
    sources: set[str] = set()
    for c in candidates:
        sources.update(c.consensus_sources)
    src_label = ", ".join(sorted(sources)) or "public sources"
    return (f"Drawn from {src_label}. Top of the consensus list: "
            f"{candidates[0].name}.")


# --- Graph ----------------------------------------------------------------------


def build_advisor_graph():
    graph = StateGraph(AgentState)
    graph.add_node("fetch_consensus", node_fetch_consensus)
    graph.add_node("enrich", node_enrich)
    graph.add_node("score", node_score)
    graph.add_node("explain", node_explain)
    graph.add_node("reason", node_reason)

    graph.set_entry_point("fetch_consensus")
    graph.add_edge("fetch_consensus", "enrich")
    graph.add_edge("enrich", "score")
    graph.add_edge("score", "explain")
    graph.add_edge("explain", "reason")
    graph.add_edge("reason", END)
    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_advisor_graph()
    return _compiled_graph


async def run_advisor(user: UserContext) -> Recommendation:
    graph = _get_graph()
    final_state: AgentState = await graph.ainvoke({"user": user})
    candidates = final_state.get("candidates", [])
    return Recommendation(
        user_context=user,
        candidates=candidates,
        top_pick_id=final_state.get("top_pick_id"),
        reasoning=final_state.get("reasoning", ""),
        explanation=final_state.get("explanation"),
        consensus_summary=final_state.get("consensus_summary"),
        factors_used=["returns_3y", "returns_5y", "expense_ratio", "aum_crore",
                       "risk_match", "consensus_rank"],
    )
