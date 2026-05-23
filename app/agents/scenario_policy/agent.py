"""Scenario & Policy Impact agent.

Single LLM call returns:
  1. A short narrative ('the backdrop' for the user's country).
  2. A tilts dict — for a closed instrument vocabulary, label each as
     tailwind / neutral / headwind based on the snapshot.

The closed instrument vocabulary lives here (not in schemas) because it's
the agent's contract with the LLM. If we want more granular tilts later,
the orchestrator narrows the vocabulary per query.
"""
from __future__ import annotations

import json
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.schemas import AgentInput, AgentOutput, CurrentScenario

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "Macro framing is illustrative — markets surprise. "
    "This is educational information, not financial advice.")

# Closed instrument vocabulary the agent is allowed to score.
INSTRUMENT_KEYS: tuple[str, ...] = (
    "equity_sip", "large_cap", "mid_cap", "small_cap",
    "flexi_cap", "debt_fund", "bonds", "gold_etf", "silver_etf",
    "international_equity", "fd",
)

_VALID_TILTS = {"tailwind", "neutral", "headwind"}


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.2,
    )


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly macro educator. Given the "
     "current scenario snapshot for a country, do TWO things:\n\n"
     "1. Write 3-5 plain-English sentences describing the macro / "
     "geopolitical backdrop. NEVER tell the user to buy or sell. End the "
     "narrative with: 'This is educational, not advice.'\n\n"
     "2. Output a strict JSON object on its own line at the very end, with "
     "the key 'tilts' whose value is a dict mapping each of these "
     "instrument keys to exactly one of 'tailwind' | 'neutral' | "
     "'headwind' based on the backdrop:\n"
     "{instrument_keys}\n\n"
     "Format STRICTLY as:\n"
     "<narrative>\n"
     "```json\n"
     "{{\"tilts\": {{...}}}}\n"
     "```"),
    ("user",
     "Country: {country}\n"
     "Refreshed at: {refreshed_at}\n"
     "Policy state: {policy}\n"
     "Market regime: {regime}\n"
     "Active events (top 5):\n{events}\n"
     "Notable headlines:\n{headlines}\n\n"
     "User context (may be empty): {user_context}\n"
     "User query (may be empty for periodic refresh): {query}\n\n"
     "Produce the narrative followed by the JSON block.")
])


async def run(input: AgentInput) -> AgentOutput:
    scenario: CurrentScenario | None = input.scenario
    if scenario is None:
        return AgentOutput(
            narrative=("No scenario snapshot is available yet. The "
                        "background refresher builds one every few hours."),
            structured={"tilts": {}},
            disclaimer=_DISCLAIMER,
        )

    try:
        chain = _PROMPT | _llm()
        response = await chain.ainvoke({
            "instrument_keys": ", ".join(INSTRUMENT_KEYS),
            "country": scenario.country,
            "refreshed_at": scenario.refreshed_at.isoformat(),
            "policy": _fmt_policy(scenario),
            "regime": _fmt_regime(scenario),
            "events": _fmt_events(scenario),
            "headlines": _fmt_headlines(scenario),
            "user_context": _fmt_user(input),
            "query": input.query or "(none)",
        })
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.debug("scenario_policy LLM failed: %s", exc)
        return AgentOutput(
            narrative=_deterministic_narrative(scenario),
            structured={"tilts": _heuristic_tilts(scenario),
                         "llm_error": str(exc)[:200]},
            disclaimer=_DISCLAIMER,
        )

    narrative, tilts = _parse_response(raw)
    if not tilts:
        tilts = _heuristic_tilts(scenario)
    return AgentOutput(
        narrative=narrative or _deterministic_narrative(scenario),
        structured={"tilts": _sanitize_tilts(tilts)},
        disclaimer=_DISCLAIMER,
    )


# --- formatters ------------------------------------------------------------

def _fmt_policy(s: CurrentScenario) -> str:
    ps = s.policy_state
    if ps is None:
        return "(unknown)"
    bits = [ps.authority]
    if ps.policy_rate is not None:
        bits.append(f"rate {ps.policy_rate}{'%' if ps.policy_rate_unit == 'percent' else ''}")
    if ps.last_move:
        bits.append(f"last move: {ps.last_move}")
    return ", ".join(bits)


def _fmt_regime(s: CurrentScenario) -> str:
    r = s.market_regime
    if r is None:
        return "(unknown)"
    bits = [r.trend, f"volatility {r.volatility_band}"]
    if r.notes:
        bits.append(r.notes)
    return ", ".join(bits)


def _fmt_events(s: CurrentScenario) -> str:
    if not s.active_events:
        return "(none)"
    return "\n".join(
        f"  - [{e.type.value}] {e.headline}" for e in s.active_events[:5])


def _fmt_headlines(s: CurrentScenario) -> str:
    if not s.notable_headlines:
        return "(none)"
    return "\n".join(f"  - {h}" for h in s.notable_headlines[:5])


def _fmt_user(input: AgentInput) -> str:
    u = input.user
    bits = []
    if u.age is not None:
        bits.append(f"age {u.age}")
    if u.risk_tolerance is not None:
        bits.append(f"risk {u.risk_tolerance.value}")
    if u.goal:
        bits.append(f"goal: {u.goal}")
    return ", ".join(bits) or "(none)"


# --- parsing + validation --------------------------------------------------

def _parse_response(raw: str) -> tuple[str, dict[str, str]]:
    """Split the LLM output into narrative and validated tilts."""
    narrative = raw
    tilts: dict[str, str] = {}
    if "```" not in raw:
        return raw.strip(), {}
    parts = raw.split("```")
    if len(parts) >= 2:
        narrative = parts[0].strip()
        json_blob = parts[1]
        if json_blob.startswith("json"):
            json_blob = json_blob[4:].strip()
        else:
            json_blob = json_blob.strip()
        try:
            parsed = json.loads(json_blob)
            t = parsed.get("tilts", {}) if isinstance(parsed, dict) else {}
            if isinstance(t, dict):
                tilts = {str(k): str(v) for k, v in t.items()}
        except (json.JSONDecodeError, ValueError):
            tilts = {}
    return narrative, tilts


def _sanitize_tilts(t: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in INSTRUMENT_KEYS:
        v = (t.get(key) or "").strip().lower()
        out[key] = v if v in _VALID_TILTS else "neutral"
    return out


# --- deterministic fallbacks ----------------------------------------------

def _heuristic_tilts(s: CurrentScenario) -> dict[str, str]:
    """A minimal, defensible tilt fallback used when the LLM is unavailable.

    Uses only the snapshot's structured fields; deliberately conservative
    (most things 'neutral')."""
    tilts: dict[str, str] = {k: "neutral" for k in INSTRUMENT_KEYS}
    # Crisis / war / crash -> gold tailwind, equity headwind.
    if s.active_events:
        ev_types = {e.type.value for e in s.active_events}
        if ev_types & {"war", "market_crash", "pandemic"}:
            tilts["gold_etf"] = "tailwind"
            tilts["silver_etf"] = "tailwind"
            tilts["small_cap"] = "headwind"
            tilts["equity_sip"] = "headwind"
    # High volatility -> small caps headwind.
    r = s.market_regime
    if r and r.volatility_band in {"elevated", "high"}:
        tilts["small_cap"] = "headwind"
    # Policy rate up -> bond prices down (existing holdings); FDs slightly tailwind.
    ps = s.policy_state
    if ps and ps.last_move and "hike" in ps.last_move.lower():
        tilts["bonds"] = "headwind"
        tilts["fd"] = "tailwind"
    return tilts


def _deterministic_narrative(s: CurrentScenario) -> str:
    parts: list[str] = []
    if s.policy_state and s.policy_state.policy_rate is not None:
        parts.append(
            f"{s.policy_state.authority} policy rate is at "
            f"{s.policy_state.policy_rate}%.")
    if s.market_regime:
        parts.append(
            f"Markets are in a {s.market_regime.trend} regime with "
            f"{s.market_regime.volatility_band} volatility.")
    if s.active_events:
        top = s.active_events[0]
        parts.append(f"Active event: {top.headline}.")
    parts.append("This is educational, not advice.")
    return " ".join(parts) if parts else "Background is quiet today."
