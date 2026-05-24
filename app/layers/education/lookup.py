"""Education module: serves beginner-friendly explanations from the knowledge
graph and enriches each 'affecting entity' with the current live value from
the appropriate data source.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.layers.market_data import get_source
from app.layers.market_data.base import MacroSource
from app.schemas import AffectingEntity, Explanation

_KG_PATH = Path(__file__).parent / "knowledge_graph.json"


@lru_cache
def _load_kg() -> dict:
    with _KG_PATH.open() as f:
        return json.load(f)


_ALIASES = {
    "sips": "sip",
    "systematic investment plan": "sip",
    "mf": "mutual_fund",
    "mfs": "mutual_fund",
    "mutual funds": "mutual_fund",
    "mutual fund": "mutual_fund",
    "stocks": "stock",
    "shares": "stock",
    "share": "stock",
    "equity": "stock",
    "equities": "stock",
    "etfs": "etf",
    "exchange traded fund": "etf",
    "exchange-traded fund": "etf",
    "bonds": "bond",
    "ncds": "ncd",
    "fds": "fd",
    "fixed deposit": "fd",
    "fixed deposits": "fd",
    "gold etfs": "gold_etf",
    "gold etf": "gold_etf",
}


def _resolve_entry(kg: dict, raw_term: str):
    t = raw_term.lower().strip()
    if not t:
        return None
    if t in kg:
        return kg[t]
    if t in _ALIASES and _ALIASES[t] in kg:
        return kg[_ALIASES[t]]
    underscored = t.replace(" ", "_")
    if underscored in kg:
        return kg[underscored]
    # last-ditch: try first token
    first = t.split(" ")[0]
    return kg.get(first)


async def explain(term: str, country: str = "IN") -> Explanation | None:
    """Look up a term in the knowledge graph and enrich with live data."""
    kg = _load_kg()
    entry = _resolve_entry(kg, term)
    if not entry:
        return None
    entities: list[AffectingEntity] = []
    for raw in entry["affecting_entities"]:
        live_value = await _resolve_live_value(raw.get("data_source"),
                                                 raw["name"], country)
        entities.append(AffectingEntity(
            name=raw["name"],
            description=raw["description"],
            direction=raw["direction"],
            data_source=raw.get("data_source"),
            current_value=live_value,
            impact_level=raw.get("impact_level", "moderate"),
        ))
    return Explanation(
        term=term,
        plain_english=entry["plain_english"],
        why_it_matters=entry["why_it_matters"],
        affecting_entities=entities,
        related_terms=entry.get("related_terms", []),
    )


async def _resolve_live_value(source_id: str | None, entity_name: str,
                                country: str) -> str | None:
    """Best-effort: fetch a current value from the relevant data source."""
    if not source_id:
        return None
    if source_id in {"manual_research", "user_input", "instrument_metadata"}:
        return None
    macro_id = _macro_for_country(source_id, country)
    if macro_id:
        src = get_source(macro_id)
        if isinstance(src, MacroSource):
            try:
                points = await src.get_indicators(country)
            except Exception:
                return None
            for p in points:
                if _matches(entity_name, p.indicator):
                    return f"{p.value:.2f} {p.unit or ''}".strip()
    return None


def _macro_for_country(source_id: str, country: str) -> str | None:
    if source_id == "rbi":
        return "rbi" if country == "IN" else None
    if source_id == "fred":
        return "fred" if country == "US" else None
    if source_id == "rbi_or_fred":
        return "rbi" if country == "IN" else "fred" if country == "US" else "world_bank"
    if source_id == "fred_or_rbi":
        return _macro_for_country("rbi_or_fred", country)
    return None


def _matches(query: str, candidate: str) -> bool:
    q = query.lower()
    c = candidate.lower()
    keywords = ["repo", "cpi", "inflation", "fed funds", "treasury", "gdp", "unemployment"]
    for kw in keywords:
        if kw in q and kw in c:
            return True
    return False
