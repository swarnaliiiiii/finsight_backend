"""Event classifier: headline -> Event (or None if not noteworthy).

Layer-level LLM use is fine — layers can call models; they just can't call
agents. This keeps event classification cheap (one LLM call per refresh,
not per query) and out of the per-request hot path.

Fallback: when no LLM is configured or the call fails, the keyword tagger
runs instead. The scenario layer keeps producing valid snapshots either way.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.schemas import Event, EventType

logger = logging.getLogger(__name__)

# Keyword fallback (also serves as a hint set for the LLM prompt).
_KEYWORDS: list[tuple[EventType, tuple[str, ...]]] = [
    (EventType.WAR, ("war", "invasion", "ceasefire", "military strike")),
    (EventType.GEOPOLITICAL, ("sanctions", "tariff", "geopolitical", "border")),
    (EventType.MONETARY_POLICY, ("rate cut", "rate hike", "repo rate",
                                  "fed funds", "rbi policy", "fomc")),
    (EventType.FISCAL_POLICY, ("budget", "fiscal", "deficit")),
    (EventType.REGULATORY, ("sebi", "regulator", "ruling", "compliance order")),
    (EventType.INFLATION_SHOCK, ("inflation", "cpi", "wpi")),
    (EventType.MARKET_CRASH, ("crash", "plunge", "selloff", "circuit breaker")),
    (EventType.PANDEMIC, ("pandemic", "outbreak", "epidemic")),
    (EventType.ELECTION, ("election", "poll result", "general election")),
]

_VALID_TYPES = {t.value for t in EventType}


def _keyword_classify(headline: str) -> EventType | None:
    h = headline.lower()
    for ev_type, kws in _KEYWORDS:
        if any(kw in h for kw in kws):
            return ev_type
    return None


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Classify a single news headline as ONE event category, or 'none' if "
     "the headline is not a noteworthy market-moving event. Reply with ONLY "
     "the category string, no punctuation.\n\n"
     "Categories:\n"
     "- war | geopolitical | monetary_policy | fiscal_policy | regulatory\n"
     "- inflation_shock | market_crash | pandemic | election | budget\n"
     "- none"),
    ("user", "Headline: {headline}")
])


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.0,
    )


async def classify_event(headline: str, *, url: str | None = None,
                           published_at: datetime | None = None
                           ) -> Event | None:
    """Return a typed Event for `headline`, or None if it's not noteworthy."""
    if not headline:
        return None

    # Try the LLM first; fall through to keywords on any failure.
    ev_type: EventType | None = None
    if settings.GROQ_API_KEY:
        try:
            chain = _PROMPT | _llm()
            response = await chain.ainvoke({"headline": headline})
            raw = (response.content if hasattr(response, "content")
                    else str(response)).strip().lower().strip(".\"'`")
            if raw in _VALID_TYPES:
                ev_type = EventType(raw)
            elif raw == "none":
                ev_type = None
            else:
                ev_type = _keyword_classify(headline)
        except Exception as exc:
            logger.debug("event classifier LLM failed; falling back: %s", exc)
            ev_type = _keyword_classify(headline)
    else:
        ev_type = _keyword_classify(headline)

    if ev_type is None:
        return None

    return Event(
        id=hashlib.sha1(headline.encode("utf-8")).hexdigest()[:12],
        type=ev_type,
        headline=headline,
        summary=headline,
        started_at=published_at,
        sources=[url] if url else [],
    )
