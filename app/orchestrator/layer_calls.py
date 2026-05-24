"""Whitelisted layer-call wrappers.

Plan steps reference layer calls by NAME (string). The runner looks the name
up in `LAYER_CALLS` here. This is the only place where layers are reached
from the orchestrator side — agents never see these functions because they
can't import this module (it lives under orchestrator/).

Each wrapper:
  - takes (ctx: RunContext) -> writes results into ctx.accumulator
  - is cheap to add: new capability == one new function + one registry entry
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.core.geography import price_sources_for
from app.layers.education import explain as education_explain
from app.layers.historical import (compute_era_performance, find_era,
                                      resolve_ticker)
from app.layers.brief_signals import (macro_movements, market_pulse,
                                          trending_news)
from app.layers.market_data import get_sources_by_name
from app.layers.market_data.base import PriceSource
from app.layers.memory import (readout as memory_readout, record_activity,
                                  record_turn)
from app.layers.projection import (allocation_for_profile, monte_carlo_sip,
                                      sip_future_value)
from app.layers.recommender import (compare_candidates, consensus_fetcher,
                                       curated_candidates,
                                       enrich as recommender_enrich,
                                       score_candidates)
from app.layers.scenario import scenario_store
from app.layers.search import find_videos, vector_search, web_search
from app.layers.sentiment import crowd_picks_for_instrument
from app.orchestrator.budget import QueryBudget
from app.schemas import (HistoricalReport, InstrumentType, Intent,
                          UserContext)


@dataclass
class RunContext:
    """Mutable bundle threaded through plan execution. The orchestrator owns
    this — agents never see it (they receive a frozen AgentInput built from
    its accumulator)."""
    query: str
    user: UserContext
    budget: QueryBudget
    user_id: str | None = None
    session_id: str | None = None
    accumulator: dict[str, Any] = field(default_factory=dict)

    def stash(self, key: str, value: Any) -> None:
        self.accumulator[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.accumulator.get(key, default)


# --- layer-call implementations -------------------------------------------

async def _call_scenario_snapshot(ctx: RunContext) -> None:
    snap = scenario_store.get(ctx.user.country)
    ctx.stash("scenario", snap)


async def _call_education_explain(ctx: RunContext) -> None:
    """Look up the term the user is asking about and stash the layer's
    structured Explanation (or None if the term isn't in the KG)."""
    term = ctx.get("term") or _guess_term(ctx.query)
    if not term:
        ctx.stash("explanation", None)
        return
    result = await education_explain(term, country=ctx.user.country)
    ctx.stash("term", term)
    ctx.stash("explanation", result)


def _guess_term(query: str) -> str | None:
    """Cheap term extractor for queries like 'what is sip', 'explain etf',
    'how do I start a SIP', 'tell me about gold ETFs'.

    Strategy:
      1. Strip known leading question-phrase prefixes (longest first).
      2. From the remainder, strip a few filler words at the start
         ('a ', 'an ', 'the ', 'i ', 'i ', 'me ', 'how to ', 'about ', etc.).
      3. Try the remaining phrase as a key, then progressively the first
         two / first one token(s). The KG is matched against any of those.
      4. If nothing matches, return the best candidate (single token) so the
         caller still has something — but it may be unknown to the KG.
    """
    q = query.lower().strip()
    # Longest prefixes first so "how to start a " wins over "how to ".
    prefixes = sorted(
        [
            "what is a ", "what is an ", "what is ", "what's a ",
            "what's an ", "what's ", "explain ",
            "tell me about ", "tell me ", "about ",
            "how does a ", "how does an ", "how does ",
            "how do a ", "how do an ", "how do i ", "how do you ", "how do ",
            "how can i ", "how can you ", "how to start a ", "how to start an ",
            "how to start ", "how to open a ", "how to open an ", "how to open ",
            "how to buy a ", "how to buy an ", "how to buy ",
            "how to invest in a ", "how to invest in an ", "how to invest in ",
            "how to set up a ", "how to set up ", "how to ",
            "what are a ", "what are an ", "what are ",
        ],
        key=len,
        reverse=True,
    )
    for prefix in prefixes:
        if q.startswith(prefix):
            q = q[len(prefix):]
            break

    # Strip light filler at the start of what remains.
    filler = ("i ", "you ", "we ", "to ", "a ", "an ", "the ", "my ",
                "start a ", "start an ", "start ", "open a ", "open an ",
                "open ", "buy a ", "buy an ", "buy ", "invest in a ",
                "invest in an ", "invest in ", "set up a ", "set up an ",
                "set up ", "about ")
    # Iterate until nothing more strips (e.g. "i start a sip" -> "start a sip"
    # -> "sip").
    for _ in range(6):
        changed = False
        for f in filler:
            if q.startswith(f):
                q = q[len(f):]
                changed = True
                break
        if not changed:
            break

    q = q.strip(" ?.!,;:'\"")
    if not q:
        return None
    return q


# --- projection layer-calls ------------------------------------------------

_DEFAULT_ASSUMED_RETURN = 0.12  # illustrative; the agent flags this as an assumption


async def _call_projection_sip_fv(ctx: RunContext) -> None:
    """Deterministic SIP future value. Pulls monthly + years from either the
    UserContext or by parsing them out of the free-form query."""
    monthly, years = _resolve_amount_and_horizon(ctx)
    if monthly is None or years is None:
        ctx.stash("projection", None)
        return
    ctx.stash("projection",
               sip_future_value(monthly, _DEFAULT_ASSUMED_RETURN, years))


async def _call_projection_monte_carlo(ctx: RunContext) -> None:
    """Monte Carlo range for an SIP. Same inputs as projection.sip_fv."""
    monthly, years = _resolve_amount_and_horizon(ctx)
    if monthly is None or years is None:
        ctx.stash("projection_range", None)
        return
    ctx.stash("projection_range",
               monte_carlo_sip(monthly, years, seed=1234))


async def _call_projection_allocation(ctx: RunContext) -> None:
    """Rule-based allocation for the user's profile."""
    plan = allocation_for_profile(
        age=ctx.user.age,
        risk=ctx.user.risk_tolerance,
        target_monthly=ctx.user.amount,
    )
    ctx.stash("allocation", plan)


# --- search layer-calls ----------------------------------------------------

async def _call_search_web(ctx: RunContext) -> None:
    """General web search keyed off the user's free-form query. Decrements
    the per-query search budget (separate from the layer-call counter)."""
    try:
        ctx.budget.spend_search()
    except Exception:
        return
    docs = await web_search(ctx.query, country=ctx.user.country, limit=6)
    _append_documents(ctx, docs)


async def _call_search_term_resources(ctx: RunContext) -> None:
    """Resource curation for an EXPLAIN_TERM-style query: one combined web
    search ('best beginner explainer <term> India 2026') that picks up both
    articles and videos. Cheap — single Tavily call, no YouTube quota."""
    term = ctx.get("term")
    if not term:
        return
    try:
        ctx.budget.spend_search()
    except Exception:
        return
    q = (f"best beginner explainer {term} {ctx.user.country} 2026 "
          "(article OR video)")
    docs = await web_search(q, country=ctx.user.country, limit=6)
    _append_documents(ctx, docs)


async def _call_search_videos(ctx: RunContext) -> None:
    """Explicit YouTube curation. Burns YouTube quota (~100 units) so the
    runner uses this only when the plan really wants video results."""
    term = ctx.get("term") or ctx.query
    if not term:
        return
    docs = await find_videos(term, country=ctx.user.country, limit=4)
    _append_documents(ctx, docs)


async def _call_search_vector(ctx: RunContext) -> None:
    """Semantic retrieval over ingested SEBI/AMC docs. Falls back to keyword
    matching when no embedding provider is configured."""
    try:
        ctx.budget.spend_search()
    except Exception:
        return
    docs = await vector_search(ctx.query, k=4)
    _append_documents(ctx, docs)


# --- memory layer-calls ----------------------------------------------------

async def _call_memory_readout(ctx: RunContext) -> None:
    """Load persistent profile + recent turns + recent activity for the
    user. Stashes the result under `memory_readout` for agents AND hydrates
    UserContext with any persisted fields the request didn't override."""
    if not ctx.user_id:
        return
    readout = await memory_readout(ctx.user_id, country=ctx.user.country)
    ctx.stash("memory_readout", readout)

    # Hydrate UserContext: persisted fields fill in where the request was silent.
    p = readout.profile
    u = ctx.user
    new = u.model_dump()
    fills = {
        "age": p.age,
        "risk_tolerance": p.risk_tolerance,
        "goal": p.goal,
        "income_bracket": p.income_bracket,
        "comprehension_level": p.comprehension_level,
        "instrument_type": p.instrument_type,
        "amount": p.amount,
        "horizon_years": p.horizon_years,
    }
    changed = False
    for k, v in fills.items():
        if new.get(k) in (None, "") and v is not None:
            new[k] = v
            changed = True
    if changed:
        ctx.user = UserContext(**new)


async def _call_memory_record_turn(ctx: RunContext) -> None:
    """Persist this turn. Runs at the end of every plan — the envelope is
    pulled from the assembly agent's output once it lands."""
    if not ctx.user_id or not ctx.session_id:
        return
    outputs = ctx.accumulator.get("__agent_outputs__", {}) or {}
    assembly_out = outputs.get("assembly")
    envelope: dict[str, Any] = {}
    if assembly_out is not None:
        env_val = assembly_out.structured.get("envelope")
        if isinstance(env_val, dict):
            envelope = env_val
    intent = ctx.accumulator.get("intent") or Intent.UNKNOWN
    if not isinstance(intent, Intent):
        try:
            intent = Intent(intent)
        except ValueError:
            intent = Intent.UNKNOWN
    await record_turn(
        user_id=ctx.user_id,
        session_id=ctx.session_id,
        query=ctx.query,
        intent=intent,
        envelope=envelope,
    )


async def _call_memory_record_activity(ctx: RunContext) -> None:
    """Record a coarse-grained activity event derived from the current plan
    outputs. Cheap; runs alongside record_turn."""
    if not ctx.user_id:
        return
    intent = ctx.accumulator.get("intent")
    event_type = {
        Intent.EXPLAIN_TERM: "term_viewed",
        Intent.QUICK_FACT: "fact_viewed",
        Intent.PROJECT_RETURNS: "projection_run",
        Intent.RECOMMEND_INSTRUMENT: "recommendation_viewed",
        Intent.HISTORICAL_BEHAVIOR: "historical_viewed",
        Intent.CURRENT_NEWS: "news_viewed",
        Intent.COMPARE_INSTRUMENTS: "comparison_run",
        Intent.DAILY_BRIEF: "brief_viewed",
    }.get(intent if isinstance(intent, Intent) else None)
    if event_type is None:
        return
    payload: dict[str, Any] = {"query": ctx.query[:300]}
    if term := ctx.get("term"):
        payload["term"] = term
    if (report := ctx.get("historical_report")) is not None:
        payload["ticker"] = getattr(report, "ticker", None)
        payload["era_id"] = getattr(getattr(report, "era", None), "id", None)
    await record_activity(user_id=ctx.user_id, event_type=event_type,
                            payload=payload)


# --- brief layer-call ------------------------------------------------------

async def _call_brief_gather(ctx: RunContext) -> None:
    """Gather signals (market pulse + macro movements + trending news) for
    the user's country. Used by the DAILY_BRIEF plan."""
    import asyncio as _asyncio
    country = ctx.user.country
    pulse, macros, news = await _asyncio.gather(
        market_pulse(country),
        macro_movements(country),
        trending_news(country, limit=10),
        return_exceptions=True,
    )
    signals: list = []
    if not isinstance(pulse, Exception) and pulse is not None:
        signals.append(pulse)
    if isinstance(macros, list):
        signals.extend(macros)
    if isinstance(news, list):
        signals.extend(news)
    ctx.stash("brief_signals", signals)


# --- recommender layer-calls ----------------------------------------------

# Cheap heuristic so COMPARE_INSTRUMENTS / INSTRUMENT_STARTER work without a
# structured field. Order matters: 'gold etf' / 'silver etf' must match BEFORE
# plain 'etf' so a query like "gold ETF vs silver" resolves to ETF (not SIP).
_INSTRUMENT_HINTS: list[tuple[InstrumentType, tuple[str, ...]]] = [
    (InstrumentType.ETF,  ("gold etf", "gold etfs", "silver etf",
                              "silver etfs", "index fund", "nifty etf",
                              "etf", "etfs")),
    (InstrumentType.SIP,  ("sip", "sips", "systematic investment")),
    (InstrumentType.MUTUAL_FUND, ("mutual fund", "mutual funds", "mf ",
                                    "elss", "flexi-cap", "flexi cap",
                                    "large-cap fund", "large cap fund",
                                    "small-cap fund", "small cap fund")),
    (InstrumentType.STOCK, ("stock", "stocks", "share", "shares",
                              "equity", "equities")),
    (InstrumentType.BOND,  ("bond", "bonds", "g-sec", "gilt", "sgb",
                              "sovereign gold bond")),
    (InstrumentType.NCD,   ("ncd", "ncds")),
    (InstrumentType.FD,    ("fixed deposit", "fixed deposits", " fd ",
                              "fd ", " fd")),
]


def _resolve_instrument(ctx: RunContext) -> InstrumentType | None:
    if ctx.user.instrument_type is not None:
        return ctx.user.instrument_type
    q = " " + ctx.query.lower() + " "
    for inst, kws in _INSTRUMENT_HINTS:
        if any(kw in q for kw in kws):
            return inst
    return None


def _detect_two_instruments(query: str) -> list[InstrumentType]:
    """Best-effort: pull all instrument tokens from the query in order of
    appearance. 'Gold ETF vs Silver ETF' -> [ETF]. 'SIP vs FD' -> [SIP, FD]."""
    q = " " + query.lower() + " "
    found: list[InstrumentType] = []
    for inst, kws in _INSTRUMENT_HINTS:
        if any(kw in q for kw in kws) and inst not in found:
            found.append(inst)
        if len(found) >= 2:
            break
    return found


async def _call_recommender_consensus(ctx: RunContext) -> None:
    """Fetch consensus candidates for the (instrument, country, category).
    Stashes the raw list under `candidates`.

    Order of preference:
      1. Live scrape (Groww / ValueResearch / Tavily depending on country).
      2. Curated beginner-pick fallback so the caller is never empty.
    """
    inst = _resolve_instrument(ctx) or InstrumentType.SIP
    results: list = []
    try:
        results = await consensus_fetcher.fetch(
            instrument_type=inst,
            country=ctx.user.country,
            category=ctx.user.goal,
        )
    except Exception:
        results = []
    if not results:
        results = curated_candidates(inst, ctx.user.country)
    ctx.stash("instrument_type_resolved", inst)
    ctx.stash("candidates", results[:8])


async def _call_recommender_enrich(ctx: RunContext) -> None:
    """Fill in returns/expense/AUM/risk for each candidate."""
    cs = ctx.get("candidates") or []
    if not cs:
        return
    try:
        enriched = await recommender_enrich(cs, ctx.user.country)
    except Exception:
        enriched = cs
    ctx.stash("candidates", enriched)


async def _call_recommender_score(ctx: RunContext) -> None:
    """Rank the candidates against the user profile."""
    cs = ctx.get("candidates") or []
    if not cs:
        return
    ranked = score_candidates(cs, ctx.user)
    ctx.stash("candidates", ranked)


async def _call_recommender_compare(ctx: RunContext) -> None:
    """Build a side-by-side Comparison from the ranked candidates."""
    cs = ctx.get("candidates") or []
    if not cs:
        return
    ctx.stash("comparison", compare_candidates(cs[:6]))


# --- sentiment (crowd) layer-call -----------------------------------------

async def _call_sentiment_crowd(ctx: RunContext) -> None:
    """Curated 'what other beginners do' picks for the resolved instrument.
    Hardcoded for v1 — see app/layers/sentiment/crowd.py."""
    inst = ctx.get("instrument_type_resolved")
    if not inst:
        inst = _resolve_instrument(ctx) or InstrumentType.SIP
    key = inst.value if isinstance(inst, InstrumentType) else str(inst)
    ctx.stash("crowd_picks", crowd_picks_for_instrument(key))


# --- historical layer-call -------------------------------------------------

async def _call_historical_era_performance(ctx: RunContext) -> None:
    """End-to-end historical lookup:
      1. Match era from the free-form query.
      2. Resolve a representative ticker for the mentioned instrument.
      3. Fetch the price history covering the era.
      4. Compute window stats.
    Failures leave `historical_report` as None — the agent handles it.
    """
    era = find_era(ctx.query, country=ctx.user.country)
    if era is None:
        ctx.stash("historical_report", None)
        return

    ticker, label = resolve_ticker(ctx.query, ctx.user.country)
    if ticker is None:
        ctx.stash("historical_report", HistoricalReport(
            era=era, instrument_label=label, ticker="",
            performance=None,
        ))
        return

    # Fetch a long-enough history window. yfinance accepts 'max' or year
    # offsets; we ask for max and let the analytics filter to the era.
    sources = [s for s in get_sources_by_name(
                  price_sources_for(ctx.user.country))
                if isinstance(s, PriceSource)]
    points = []
    for src in sources:
        try:
            points = await src.get_history(ticker, period="max")
        except Exception:
            points = []
        if points:
            break

    perf = compute_era_performance(ticker, era, points) if points else None
    ctx.stash("historical_report", HistoricalReport(
        era=era,
        instrument_label=label,
        ticker=ticker,
        performance=perf,
    ))


def _append_documents(ctx: RunContext, docs: list) -> None:
    existing = ctx.get("documents") or []
    seen = {(d.url or d.title).lower() for d in existing}
    for d in docs:
        key = (d.url or d.title).lower()
        if key in seen:
            continue
        seen.add(key)
        existing.append(d)
    ctx.stash("documents", existing)


# --- input parsers ---------------------------------------------------------

_AMOUNT_RE = re.compile(
    r"(?:invest|put|save)\s+(?:rs\.?|₹|\$|£)?\s?([\d,]+(?:\.\d+)?)"
    r"(?:\s?(k|lakh|crore|cr|l))?", re.I)
_HORIZON_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:year|yr|y)s?\b", re.I)
_SCALE = {"k": 1_000, "l": 100_000, "lakh": 100_000, "cr": 10_000_000,
           "crore": 10_000_000}


def _resolve_amount_and_horizon(ctx: RunContext) -> tuple[float | None,
                                                              float | None]:
    """Use UserContext fields first; fall back to parsing the NL query."""
    monthly = ctx.user.amount
    years: float | None = (float(ctx.user.horizon_years)
                            if ctx.user.horizon_years is not None else None)
    if monthly is None:
        m = _AMOUNT_RE.search(ctx.query)
        if m:
            try:
                amt = float(m.group(1).replace(",", ""))
                scale = (_SCALE.get(m.group(2).lower(), 1)
                          if m.group(2) else 1)
                monthly = amt * scale
            except (ValueError, AttributeError):
                pass
    if years is None:
        m = _HORIZON_RE.search(ctx.query)
        if m:
            try:
                years = float(m.group(1))
            except ValueError:
                pass
    return monthly, years


# --- registry --------------------------------------------------------------

LayerCall = Callable[[RunContext], Awaitable[None]]

LAYER_CALLS: dict[str, LayerCall] = {
    "scenario.snapshot": _call_scenario_snapshot,
    "education.explain": _call_education_explain,
    "projection.sip_future_value": _call_projection_sip_fv,
    "projection.monte_carlo": _call_projection_monte_carlo,
    "projection.allocation": _call_projection_allocation,
    "search.web": _call_search_web,
    "search.term_resources": _call_search_term_resources,
    "search.videos": _call_search_videos,
    "search.vector": _call_search_vector,
    "historical.era_performance": _call_historical_era_performance,
    "memory.readout": _call_memory_readout,
    "memory.record_turn": _call_memory_record_turn,
    "memory.record_activity": _call_memory_record_activity,
    "recommender.consensus": _call_recommender_consensus,
    "recommender.enrich": _call_recommender_enrich,
    "recommender.score": _call_recommender_score,
    "recommender.compare": _call_recommender_compare,
    "sentiment.crowd": _call_sentiment_crowd,
    "brief.gather": _call_brief_gather,
}
