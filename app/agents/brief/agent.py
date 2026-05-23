"""Daily Brief agent.

Inputs:
  - input.upstream['brief_signals'] : list[Signal] from the brief_signals layer
  - input.user.country              : drives locale / market index

Output:
  - narrative : one-line market summary
  - structured: {'items': [BriefItem...], 'market_summary': str}
                Assembly will render the items as ListBlock entries.
"""
from __future__ import annotations

import json
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.core.geography import market_locale
from app.schemas import (AgentInput, AgentOutput, BriefItem, BriefSourceType,
                          Signal)

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "Educational information based on public data, not financial advice. "
    "Markets move daily — don't make snap decisions on a single brief.")


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )


_POLISH_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly financial educator writing the "
     "Daily Brief for a user in {country} ({market}, {currency}). Transform "
     "raw signals into 3 plain-English action items. NEVER tell the user to "
     "buy or sell. Use phrases like 'worth watching', 'this can affect "
     "your...', 'most beginners would...'. Return STRICT JSON only, no "
     "markdown fences. Schema:\n"
     '[\n  {{"title": "short headline (under 90 chars)",\n    '
     '"plain_english": "1-2 sentence explanation a first-time investor understands",\n    '
     '"why_it_matters": "one sentence tying this to the user\'s instruments"\n  }},\n  ...\n]'),
    ("user",
     "Raw signals (ordered by importance):\n\n{signals}\n\n"
     "Produce exactly {n} items as a JSON array. Each item should be tied "
     "to the affected_instruments listed in the signal where possible.")
])

_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Write ONE sentence (under 160 chars) summarising today's market mood "
     "for a beginner investor in {country}. Calm, factual tone. Mention "
     "{market} only if relevant. NEVER predict or advise."),
    ("user", "Today's signals:\n{signals}")
])


async def run(input: AgentInput) -> AgentOutput:
    signals: list[Signal] = input.upstream.get("brief_signals") or []
    country = input.user.country
    locale = market_locale(country)  # type: ignore[arg-type]

    if not signals:
        return AgentOutput(
            narrative=("Markets are quiet today — a good moment to review the "
                        "basics."),
            structured={"items": [], "market_summary": ""},
            disclaimer=_DISCLAIMER,
        )

    top = _rank(signals)
    items = await _polish_items(top, country, locale)
    summary = await _summary(items, country, locale)

    return AgentOutput(
        narrative=summary,
        structured={
            "items": [it.model_dump() for it in items],
            "market_summary": summary,
        },
        disclaimer=_DISCLAIMER,
    )


# --- helpers --------------------------------------------------------------

def _rank(signals: list[Signal]) -> list[Signal]:
    signals_sorted = sorted(signals, key=lambda s: s.importance_score,
                              reverse=True)
    top: list[Signal] = []
    seen_types: set[BriefSourceType] = set()
    for s in signals_sorted:
        if s.source_type in seen_types:
            continue
        top.append(s)
        seen_types.add(s.source_type)
        if len(top) >= 3:
            break
    for s in signals_sorted:
        if len(top) >= 3:
            break
        if s in top:
            continue
        top.append(s)
    return top[:3]


async def _polish_items(top: list[Signal], country: str,
                         locale: dict) -> list[BriefItem]:
    raw_text = "\n\n".join(
        f"Signal {i+1} [{s.source_type.value}, severity={s.severity.value}]:\n"
        f"  {s.raw_data}\n"
        f"  affected_instruments={[ai.value for ai in s.affected_instruments]}"
        for i, s in enumerate(top)
    )
    try:
        chain = _POLISH_PROMPT | _llm()
        response = await chain.ainvoke({
            "country": country,
            "market": locale["primary_index"],
            "currency": locale["currency"],
            "signals": raw_text,
            "n": len(top),
        })
        content = (response.content if hasattr(response, "content")
                    else str(response))
    except Exception:
        logger.exception("brief.polish failed; using deterministic fallback")
        return [_fallback_item(s) for s in top]
    return _parse_items(content, top)


def _parse_items(llm_response: str, signals: list[Signal]) -> list[BriefItem]:
    cleaned = llm_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if cleaned.count("```") >= 2 \
                    else cleaned
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


async def _summary(items: list[BriefItem], country: str,
                     locale: dict) -> str:
    if not items:
        return ""
    bullets = "\n".join(f"- {it.title}" for it in items)
    try:
        chain = _SUMMARY_PROMPT | _llm()
        response = await chain.ainvoke({
            "country": country,
            "market": locale["primary_index"],
            "signals": bullets,
        })
        content = (response.content if hasattr(response, "content")
                    else str(response))
        return content.strip().strip('"')[:200]
    except Exception:
        return f"{len(items)} items worth watching in {country} today."
