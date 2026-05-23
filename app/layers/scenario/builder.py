"""Compose a `CurrentScenario` snapshot for a country.

Pulls from market_data (index quote, macro indicators) and news sources, then
structures the result into the typed `CurrentScenario` schema. No LLM calls,
no agent invocations — pure I/O + rule-based event tagging.

Failure tolerance: each individual source is wrapped; a single bad source
yields a partial-but-valid snapshot rather than crashing the refresh loop.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

from app.core.geography import (macro_sources_for, market_locale,
                                  news_sources_for, price_sources_for)
from app.layers.market_data import get_sources_by_name
from app.layers.market_data.base import (MacroSource, NewsSource, PriceSource)
from app.schemas import (CurrentScenario, Event, EventType, MarketRegime,
                          PolicyState)

_COUNTRY_INDEX_TICKER: dict[str, str] = {
    "IN": "^NSEI",
    "US": "^GSPC",
    "UK": "^FTSE",
}

# Coarse keyword -> EventType mapping for the layer-level tagger. The
# Scenario & Policy Impact *agent* (step 9) will do nuanced classification;
# this exists so the snapshot ships with usable structure on day one.
_EVENT_KEYWORDS: list[tuple[EventType, tuple[str, ...]]] = [
    (EventType.WAR, ("war", "invasion", "ceasefire", "military strike")),
    (EventType.GEOPOLITICAL, ("sanctions", "tariff", "geopolitical", "border")),
    (EventType.MONETARY_POLICY, ("rate cut", "rate hike", "repo rate", "fed funds",
                                  "rbi policy", "fomc")),
    (EventType.FISCAL_POLICY, ("budget", "fiscal", "deficit")),
    (EventType.REGULATORY, ("sebi", "regulator", "ruling", "compliance order")),
    (EventType.INFLATION_SHOCK, ("inflation", "cpi", "wpi")),
    (EventType.MARKET_CRASH, ("crash", "plunge", "selloff", "circuit breaker")),
    (EventType.PANDEMIC, ("pandemic", "outbreak", "epidemic")),
    (EventType.ELECTION, ("election", "poll result", "general election")),
]


async def build_scenario(country: str) -> CurrentScenario:
    """Compose a snapshot for one country. Best-effort: per-source failures
    do not abort the whole snapshot."""
    regime_task = _safe(_build_market_regime(country))
    policy_task = _safe(_build_policy_state(country))
    headlines_task = _safe(_fetch_headlines(country))

    regime, policy, headlines = await asyncio.gather(
        regime_task, policy_task, headlines_task)

    headlines = headlines or []
    events = _classify_events(headlines)

    return CurrentScenario(
        refreshed_at=datetime.now(timezone.utc),
        country=country,
        active_events=events,
        market_regime=regime,
        policy_state=policy,
        instrument_tilts={},  # populated by the agent later; layer stays factual
        notable_headlines=[h["title"] for h in headlines[:5]],
    )


# --- builders --------------------------------------------------------------

async def _build_market_regime(country: str) -> MarketRegime | None:
    ticker = _COUNTRY_INDEX_TICKER.get(country)
    if not ticker:
        return None
    price_sources = [s for s in get_sources_by_name(price_sources_for(country))
                      if isinstance(s, PriceSource)]
    for src in price_sources:
        quote = await src.get_quote(ticker)
        if not quote:
            continue
        pct = quote.change_percent or 0.0
        if pct >= 0.5:
            trend = "bull"
        elif pct <= -0.5:
            trend = "bear"
        else:
            trend = "sideways"
        abs_pct = abs(pct)
        if abs_pct >= 2.0:
            vol = "elevated"
        elif abs_pct >= 1.0:
            vol = "normal"
        else:
            vol = "low"
        return MarketRegime(
            trend=trend,
            volatility_band=vol,
            notes=f"{quote.name or ticker} {pct:+.2f}% today",
        )
    return None


async def _build_policy_state(country: str) -> PolicyState | None:
    locale = market_locale(country)  # type: ignore[arg-type]
    authority = locale["rate_authority"]
    macro_sources = [s for s in get_sources_by_name(macro_sources_for(country))
                      if isinstance(s, MacroSource)]
    for src in macro_sources:
        try:
            points = await src.get_indicators(country)
        except Exception:
            continue
        for p in points:
            if _is_policy_rate(country, p.indicator):
                return PolicyState(
                    authority=authority,
                    policy_rate=float(p.value),
                    policy_rate_unit=p.unit or "percent",
                )
    return PolicyState(authority=authority)


async def _fetch_headlines(country: str) -> list[dict]:
    sources = [s for s in get_sources_by_name(news_sources_for(country))
                if isinstance(s, NewsSource)]
    tasks = [_safe_list(s.fetch_news(query=None, country=country, limit=8))
              for s in sources]
    results = await asyncio.gather(*tasks)
    items: list[dict] = []
    for res in results:
        for ni in res:
            items.append({
                "title": ni.title,
                "url": ni.url,
                "published_at": ni.published_at,
            })
    # newest first, deduped by title
    items.sort(key=lambda x: x["published_at"] or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True)
    seen: set[str] = set()
    deduped: list[dict] = []
    for it in items:
        key = (it["title"] or "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(it)
    return deduped


# --- helpers ---------------------------------------------------------------

def _is_policy_rate(country: str, indicator: str) -> bool:
    ind = indicator.lower()
    if country == "IN":
        return "repo" in ind
    if country == "US":
        return "fed funds" in ind or "federal funds" in ind
    if country == "UK":
        return "bank rate" in ind
    return False


def _classify_events(headlines: list[dict]) -> list[Event]:
    events: list[Event] = []
    for h in headlines:
        title = h.get("title") or ""
        lowered = title.lower()
        for ev_type, kws in _EVENT_KEYWORDS:
            if any(kw in lowered for kw in kws):
                events.append(Event(
                    id=_short_hash(title),
                    type=ev_type,
                    headline=title,
                    summary=title,
                    started_at=h.get("published_at"),
                    sources=[h["url"]] if h.get("url") else [],
                ))
                break  # at most one tag per headline at the layer level
    return events


def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


async def _safe(coro):
    try:
        return await coro
    except Exception:
        return None


async def _safe_list(coro) -> list:
    try:
        out = await coro
        return out if isinstance(out, list) else []
    except Exception:
        return []
