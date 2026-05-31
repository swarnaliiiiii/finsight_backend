"""Answer-mode classifier.

The `/api/answer` endpoint asks: what *shape* should the dashboard take?

Three buckets:
  - "glossary"  — pure definition ("what is repo rate", "explain expense ratio")
                  → minimal page: narrative + sources. No inputs, no projection.
  - "analysis"  — comparison or market-take ("Gold ETF vs Silver", "which is
                  better X or Y", "what's happening in tech")
                  → narrative + comparison/picks + crowd + read + sources.
                  No inputs, no projection.
  - "starter"   — actionable ("how do I start a SIP", "how to open an FD",
                  "I want to invest in bonds")
                  → full dashboard: inputs + projection + returns + allocation
                  + picks + watch + read + crowd + sources.

Strategy:
  1. Cheap rule prepass — regex on the query string. Covers the obvious cases
     without any network call.
  2. Gemini fallback (gemini-1.5-flash) for ambiguous queries.
  3. Default to "analysis" if neither resolves.

The classifier is independent of the orchestrator's existing Intent agent
(which is finer-grained: EXPLAIN_TERM, COMPARE_INSTRUMENTS, etc.). Both run;
this one decides UI shape, the other decides which layer plan to execute.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Literal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

AnswerMode = Literal["glossary", "analysis", "starter"]


# --- Rule prepass ----------------------------------------------------------

_STARTER_PATTERN = re.compile(
    r"(?=.*\b(start|begin|open|set\s*up|buy|invest\s+in|purchase|"
    r"how\s+do\s+i|how\s+can\s+i|how\s+to|i\s+want\s+to|i'?d\s+like\s+to|"
    r"should\s+i\s+(?:start|invest|buy|open))\b)"
    r"(?=.*\b(sip|mutual\s+fund|mf|elss|etf|etfs|gold\s+etf|silver\s+etf|"
    r"index\s+fund|nifty|sensex|fd|fixed\s+deposit|bond|bonds|ncd|gold|"
    r"silver|stock|stocks|share|shares|equity|fund|invest(ing|ment)?)\b)",
    re.I,
)

_GLOSSARY_PATTERN = re.compile(
    r"^\s*(?:what\s+is|what's|what\s+are|whats|define|definition\s+of|"
    r"meaning\s+of|explain|tell\s+me\s+about|in\s+simple\s+terms|"
    r"what\s+does|what\s+do)\b",
    re.I,
)

_COMPARISON_PATTERN = re.compile(
    r"\b(vs\.?|versus|compare|better|comparison|"
    r"which\s+(?:one\s+)?(?:is|should)|"
    r"difference\s+between)\b",
    re.I,
)


def _rule_classify(query: str) -> AnswerMode | None:
    q = query.strip()
    if not q:
        return None
    # Starter trumps everything — "how do I start a SIP" is actionable even
    # though it also matches "how do" patterns.
    if _STARTER_PATTERN.search(q):
        return "starter"
    # Comparisons / "which is better" → analysis.
    if _COMPARISON_PATTERN.search(q):
        return "analysis"
    # Pure definitional questions → glossary.
    if _GLOSSARY_PATTERN.search(q):
        return "glossary"
    return None


# --- Gemini fallback -------------------------------------------------------

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

_GEMINI_SYSTEM = (
    "You classify a user's investment-related question into exactly ONE "
    "of these three buckets:\n\n"
    "  glossary  - asks for a definition/explanation of a financial term "
    "or concept (e.g. 'what is repo rate', 'explain expense ratio'). "
    "Wants knowledge, NOT an action.\n\n"
    "  analysis  - asks for a comparison, market take, or research-style "
    "answer (e.g. 'Gold ETF vs Silver', 'which is better X or Y', 'what's "
    "happening in tech', 'should I worry about the AI bubble'). Wants "
    "insight, NOT a personalised plan.\n\n"
    "  starter   - asks how to take an action (start, open, buy, set up, "
    "invest in) a specific instrument (e.g. 'how do I start a SIP', 'how "
    "to open an FD', 'I want to buy gold ETFs'). Wants a personalised plan.\n\n"
    "Reply with ONLY the bucket name (one word). No punctuation, no "
    "explanation."
)

_VALID_MODES: set[str] = {"glossary", "analysis", "starter"}


async def _gemini_classify(query: str) -> AnswerMode | None:
    if not settings.GEMINI_API_KEY:
        return None
    payload = {
        "system_instruction": {"parts": [{"text": _GEMINI_SYSTEM}]},
        "contents": [
            {"role": "user", "parts": [{"text": query}]},
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 8,
        },
    }
    params = {"key": settings.GEMINI_API_KEY}
    try:
        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            r = await client.post(_GEMINI_URL, params=params, json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("gemini answer-mode classify failed")
        return None
    try:
        text = (
            data["candidates"][0]["content"]["parts"][0]["text"]
            .strip()
            .lower()
            .strip(".\"'`")
            .split()[0]
        )
    except (KeyError, IndexError, AttributeError):
        return None
    if text in _VALID_MODES:
        return text  # type: ignore[return-value]
    return None


# --- Public API ------------------------------------------------------------

async def classify_answer_mode(query: str) -> AnswerMode:
    """Return one of 'glossary' | 'analysis' | 'starter' for the given query.

    Rules first (cheap, deterministic). Gemini fallback for ambiguous cases.
    Defaults to 'analysis' if both fail.
    """
    if not query or not query.strip():
        return "analysis"
    hit = _rule_classify(query)
    if hit is not None:
        return hit
    llm_hit = await _gemini_classify(query)
    if llm_hit is not None:
        return llm_hit
    return "analysis"


# --- Pure helper for tests / smoke -----------------------------------------

def rule_classify_only(query: str) -> AnswerMode | None:
    """Exposed for unit tests + smoke. Does NOT call Gemini."""
    return _rule_classify(query)
