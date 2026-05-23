"""Intent classifier.

Hybrid:
  1. Rule pass — cheap regex/keyword match on common phrasings. Skip LLM.
  2. LLM fallback — Groq, low temperature, returns one Intent enum value.

Architectural rules (enforced by .importlinter):
  - No imports from `app.layers.*`
  - No imports from sibling agents
  - Only `app.schemas.*` + `app.config` (for the API key)
"""
from __future__ import annotations

import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.schemas import AgentInput, AgentOutput, Intent

# --- rule-based pre-pass ---------------------------------------------------

_RULES: list[tuple[Intent, re.Pattern]] = [
    # QUICK_FACT must precede EXPLAIN_TERM: "what's the repo rate today" should
    # be a quick-fact lookup, not a glossary explanation. A query qualifies if
    # it mentions BOTH a time-word and a fact-term, in either order.
    (Intent.QUICK_FACT, re.compile(
        r"(?=.*\b(today|current|right\s+now|currently|latest)\b)"
        r"(?=.*\b(repo\s+rate|interest\s+rate|inflation|cpi|"
        r"fed\s+funds|nifty|sensex|nav)\b)", re.I)),
    (Intent.EXPLAIN_TERM, re.compile(
        r"^(what\s+is|what's|explain|tell\s+me\s+about|how\s+does|how\s+do|"
        r"how\s+to\s+start|what\s+are)\b", re.I)),
    (Intent.COMPARE_INSTRUMENTS, re.compile(
        r"\b(vs\.?|versus|compare|better|or)\b", re.I)),
    (Intent.RECOMMEND_INSTRUMENT, re.compile(
        r"\b(recommend|suggest|which.*should\s+i|best\s+\w+\s+for)\b", re.I)),
    (Intent.PROJECT_RETURNS, re.compile(
        r"\b(if\s+i\s+invest|how\s+much\s+will|future\s+value|projection)\b", re.I)),
    (Intent.CURRENT_NEWS, re.compile(
        r"\b(news|happening|latest|update)\b", re.I)),
    (Intent.HISTORICAL_BEHAVIOR, re.compile(
        r"\b(during|in\s+\d{4}|historical|history|past\s+\d+\s+years?)\b", re.I)),
    (Intent.DAILY_BRIEF, re.compile(
        r"\b(daily\s+brief|morning\s+brief|today's\s+brief)\b", re.I)),
]

_VALID_INTENT_VALUES = {i.value for i in Intent}


def _rule_classify(query: str) -> Intent | None:
    for intent, pattern in _RULES:
        if pattern.search(query):
            return intent
    return None


# --- LLM fallback ----------------------------------------------------------

_LLM_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You classify a user's free-form question about Indian/US/UK personal "
     "investing into EXACTLY ONE category. Reply with ONLY the category "
     "string, no punctuation, no explanation.\n\n"
     "Categories:\n"
     "- explain_term : asks what something is (SIP, ETF, expense ratio, etc.)\n"
     "- compare_instruments : compares two or more options\n"
     "- recommend_instrument : asks which to choose, what is best\n"
     "- project_returns : asks about future value, projection, simulation\n"
     "- current_news : asks for latest news / what's happening\n"
     "- historical_behavior : asks about past performance or behaviour during an era\n"
     "- quick_fact : asks for a current data point (repo rate, NAV, etc.)\n"
     "- daily_brief : asks for the morning/daily brief\n"
     "- unknown : none of the above"),
    ("user", "{query}")
])


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.0,
    )


async def _llm_classify(query: str) -> Intent:
    chain = _LLM_PROMPT | _llm()
    response = await chain.ainvoke({"query": query})
    raw = response.content if hasattr(response, "content") else str(response)
    token = raw.strip().lower().strip(".\"'`")
    if token in _VALID_INTENT_VALUES:
        return Intent(token)
    return Intent.UNKNOWN


# --- agent entry-point -----------------------------------------------------

async def run(input: AgentInput) -> AgentOutput:
    """Classify `input.query` into an Intent.

    Result lands in `AgentOutput.structured["intent"]`. If rules matched, we
    add a `classified_by=rules` marker so the orchestrator can log it.
    """
    rule_hit = _rule_classify(input.query)
    if rule_hit is not None:
        return AgentOutput(
            structured={"intent": rule_hit.value, "classified_by": "rules"},
        )

    try:
        intent = await _llm_classify(input.query)
    except Exception as exc:  # network / key / model error -> fail safe
        return AgentOutput(
            structured={"intent": Intent.UNKNOWN.value,
                         "classified_by": "fallback",
                         "error": str(exc)[:200]},
        )

    return AgentOutput(
        structured={"intent": intent.value, "classified_by": "llm"},
    )
