"""Daily Brief Agent.

LangGraph workflow:
  gather  -> collects signals from all sources for the country
  rank    -> picks top 3 by importance + diversity
  polish  -> Groq turns raw signals into beginner-friendly BriefItems
  summary -> Groq writes a 1-2 sentence market summary line for the top of brief
"""
from __future__ import annotations

import asyncio
import json
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from app.layers.brief_signals import (Signal, macro_movements, market_pulse,
                                          trending_news)
from app.schemas import (BriefItem, BriefSeverity, BriefSourceType, DailyBrief)
from app.config import settings
from app.core.geography import market_locale


class BriefState(TypedDict, total=False):
    country: str
    signals: list[Signal]
    top_signals: list[Signal]
    items: list[BriefItem]
    market_summary: str


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )


# --- Nodes ----------------------------------------------------------------------


async def node_gather(state: BriefState) -> BriefState:
    country = state["country"]
    pulse, macros, news = await asyncio.gather(
        market_pulse(country),
        macro_movements(country),
        trending_news(country, limit=10),
        return_exceptions=True,
    )
    signals: list[Signal] = []
    if isinstance(pulse, Signal):
        signals.append(pulse)
    if isinstance(macros, list):
        signals.extend(macros)
    if isinstance(news, list):
        signals.extend(news)
    return {"signals": signals}


async def node_rank(state: BriefState) -> BriefState:
    signals = state.get("signals", [])
    if not signals:
        return {"top_signals": []}
    signals_sorted = sorted(signals, key=lambda s: s.importance_score, reverse=True)
    top: list[Signal] = []
    seen_types: set[BriefSourceType] = set()
    # First pass: pick top-scoring item per distinct source_type for diversity
    for s in signals_sorted:
        if s.source_type in seen_types:
            continue
        top.append(s)
        seen_types.add(s.source_type)
        if len(top) >= 3:
            break
    # Fill remaining slots with next highest regardless of type
    for s in signals_sorted:
        if len(top) >= 3:
            break
        if s in top:
            continue
        top.append(s)
    return {"top_signals": top[:3]}


_POLISH_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly financial educator writing the "
     "Daily Brief for a user in {country} ({market}, {currency}). "
     "Transform raw signals into 3 plain-English action items. "
     "NEVER tell the user to buy or sell. Use phrases like 'worth watching', "
     "'this can affect your...', 'most beginners would...'. "
     "Return STRICT JSON only, no markdown fences. Schema:\n"
     '[\n  {{"title": "short headline (under 90 chars)",\n    '
     '"plain_english": "1-2 sentence explanation a first-time investor understands",\n    '
     '"why_it_matters": "one sentence tying this to the user\'s instruments"\n  }},\n  ...\n]'),
    ("user",
     "Raw signals (ordered by importance):\n\n{signals}\n\n"
     "Produce exactly {n} items as a JSON array. Each item should be tied to "
     "the affected_instruments listed in the signal where possible.")
])


async def node_polish(state: BriefState) -> BriefState:
    top = state.get("top_signals", [])
    country = state["country"]
    locale = market_locale(country)  # type: ignore[arg-type]
    if not top:
        return {"items": []}
    raw_text = "\n\n".join(
        f"Signal {i+1} [{s.source_type.value}, severity={s.severity.value}]:\n"
        f"  {s.raw_data}\n"
        f"  affected_instruments={[ai.value for ai in s.affected_instruments]}"
        for i, s in enumerate(top)
    )
    chain = _POLISH_PROMPT | _llm()
    response = await chain.ainvoke({
        "country": country,
        "market": locale["primary_index"],
        "currency": locale["currency"],
        "signals": raw_text,
        "n": len(top),
    })
    content = response.content if hasattr(response, "content") else str(response)
    items = _parse_brief_items(content, top)
    return {"items": items}


def _parse_brief_items(llm_response: str, signals: list[Signal]) -> list[BriefItem]:
    cleaned = llm_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if cleaned.count("```") >= 2 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return [_fallback_item(s) for s in signals]
    items: list[BriefItem] = []
    for i, entry in enumerate(parsed[:len(signals)]):
        signal = signals[i]
        items.append(BriefItem(
            title=entry.get("title", signal.title)[:140],
            plain_english=entry.get("plain_english", signal.raw_data),
            why_it_matters=entry.get("why_it_matters",
                                       "This affects beginner-friendly instruments."),
            affected_instruments=signal.affected_instruments,
            severity=signal.severity,
            source_type=signal.source_type,
            source_links=signal.source_links,
            learn_more_terms=signal.learn_more_terms,
        ))
    return items


def _fallback_item(signal: Signal) -> BriefItem:
    return BriefItem(
        title=signal.title,
        plain_english=signal.raw_data,
        why_it_matters="See affected instruments for context.",
        affected_instruments=signal.affected_instruments,
        severity=signal.severity,
        source_type=signal.source_type,
        source_links=signal.source_links,
        learn_more_terms=signal.learn_more_terms,
    )


_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Write ONE sentence (under 160 chars) summarising today's market mood "
     "for a beginner investor in {country}. Calm, factual tone. Mention "
     "{market} only if relevant. NEVER predict or advise."),
    ("user", "Today's signals:\n{signals}")
])


async def node_summary(state: BriefState) -> BriefState:
    items = state.get("items", [])
    country = state["country"]
    locale = market_locale(country)  # type: ignore[arg-type]
    if not items:
        return {"market_summary": "Markets are quiet today — a good moment to "
                "review the basics on the Learn page."}
    bullets = "\n".join(f"- {it.title}" for it in items)
    chain = _SUMMARY_PROMPT | _llm()
    response = await chain.ainvoke({
        "country": country,
        "market": locale["primary_index"],
        "signals": bullets,
    })
    content = response.content if hasattr(response, "content") else str(response)
    return {"market_summary": content.strip().strip('"')[:200]}


# --- Graph ----------------------------------------------------------------------


def build_brief_graph():
    graph = StateGraph(BriefState)
    graph.add_node("gather", node_gather)
    graph.add_node("rank", node_rank)
    graph.add_node("polish", node_polish)
    graph.add_node("summary", node_summary)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "rank")
    graph.add_edge("rank", "polish")
    graph.add_edge("polish", "summary")
    graph.add_edge("summary", END)
    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_brief_graph()
    return _compiled_graph


async def run_brief(country: str) -> DailyBrief:
    graph = _get_graph()
    final_state: BriefState = await graph.ainvoke({"country": country})
    return DailyBrief(
        country=country,
        market_summary=final_state.get("market_summary", ""),
        items=final_state.get("items", []),
    )
