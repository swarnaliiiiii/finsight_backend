"""FinSight AI backend entrypoint.

All routes accept an `X-Country-Code` header (IN/US/UK). Mobile clients resolve
the device's geolocation on-device and send the ISO country code. This drives
which data sources are queried.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.advisor.routes import router as advisor_router
from app.config import settings
from app.brief.routes import router as brief_router
from app.core.geography import (CountryCode, country_dependency, funds_sources_for,
                                 macro_sources_for, market_locale, news_sources_for,
                                 price_sources_for)
from app.layers.companies import get_company_profile, list_companies
from app.layers.market_data import get_sources_by_name
from app.layers.market_data.base import (FundSource, MacroSource, NewsSource,
                                            PriceSource)
from app.layers.memory import close_memory, init_memory
from app.layers.scenario import (scenario_store, start_scenario_refresher,
                                    stop_scenario_refresher)
from app.layers.search import vector_ingest
from app.orchestrator import ask as orchestrator_ask
from app.orchestrator.answer_mode import classify_answer_mode
from app.orchestrator.scenario_hook import enrich_scenario_with_tilts
from app.schemas import (InstrumentType, ResponseEnvelope, RiskLevel,
                          UserContext)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hooks:
      - init the memory layer (schema bootstrap)
      - start the scenario refresher with the LLM-tilts enricher
      - reverse on shutdown
    """
    await init_memory()
    start_scenario_refresher(on_snapshot_built=enrich_scenario_with_tilts)
    try:
        yield
    finally:
        await stop_scenario_refresher()
        await close_memory()


app = FastAPI(title="FinSight AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advisor_router)
app.include_router(brief_router)


@app.get("/")
def root() -> dict:
    return {"status": "ok", "service": "finsight-ai"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@app.get("/api/locale")
def locale(country: CountryCode = Depends(country_dependency)) -> dict:
    return {"country": country, **market_locale(country)}


@app.get("/api/scenario")
def scenario(country: CountryCode = Depends(country_dependency)) -> dict:
    """Return the cached scenario snapshot for the country.
    `null` if the refresher hasn't completed its first pass yet."""
    snap = scenario_store.get(country)
    return {"country": country, "scenario": snap}


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    instrument_type: InstrumentType | None = None
    amount: float | None = Field(default=None, ge=0)
    horizon_years: int | None = Field(default=None, ge=0, le=50)
    risk_tolerance: RiskLevel | None = None
    goal: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    income_bracket: str | None = None


@app.post("/api/ask", response_model=ResponseEnvelope)
async def ask(
    body: AskRequest,
    response: Response,
    country: CountryCode = Depends(country_dependency),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> ResponseEnvelope:
    """Free-form NL endpoint. The orchestrator classifies intent, runs the
    plan, and returns a ResponseEnvelope of typed UI blocks. Optional
    structured profile fields refine the user context.

    Identity:
      - `X-User-Id`: opaque UUID; if absent, the server issues one and
        echoes it back as a response header. Clients should persist it.
      - `X-Session-Id`: opaque UUID per conversation; same fallback.
    """
    user_id = x_user_id or str(uuid.uuid4())
    session_id = x_session_id or str(uuid.uuid4())
    response.headers["X-User-Id"] = user_id
    response.headers["X-Session-Id"] = session_id

    user = UserContext(
        country=country,
        instrument_type=body.instrument_type,
        amount=body.amount,
        horizon_years=body.horizon_years,
        risk_tolerance=body.risk_tolerance,
        goal=body.goal,
        age=body.age,
        income_bracket=body.income_bracket,
    )
    return await orchestrator_ask(body.query, user, user_id=user_id,
                                     session_id=session_id)


class IngestRequest(BaseModel):
    source: str = Field(..., description="'sebi' | 'amc' | other tag")
    doc_id: str = Field(..., max_length=128)
    title: str = Field(..., max_length=300)
    text: str = Field(..., min_length=1)
    url: str | None = None
    metadata: dict | None = None


@app.post("/api/admin/ingest")
async def ingest_document(body: IngestRequest) -> dict:
    """Ingest a single document into the vector store. Intended for an
    admin / batch pipeline — wire auth before exposing publicly."""
    chunks = await vector_ingest(
        source=body.source,
        doc_id=body.doc_id,
        title=body.title,
        text=body.text,
        url=body.url,
        metadata=body.metadata,
    )
    return {"chunks": chunks, "doc_id": body.doc_id, "source": body.source}


@app.get("/api/news")
async def news(
    country: CountryCode = Depends(country_dependency),
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    sources = [s for s in get_sources_by_name(news_sources_for(country))
               if isinstance(s, NewsSource)]
    results = await asyncio.gather(
        *(s.fetch_news(query=query, country=country, limit=limit) for s in sources),
        return_exceptions=True,
    )
    items: list = []
    for res in results:
        if isinstance(res, list):
            items.extend(res)
    items.sort(key=lambda x: x.published_at, reverse=True)
    return {"country": country, "count": len(items), "items": items[:limit]}


@app.get("/api/quote/{ticker}")
async def quote(ticker: str, country: CountryCode = Depends(country_dependency)) -> dict:
    sources = [s for s in get_sources_by_name(price_sources_for(country))
               if isinstance(s, PriceSource)]
    for src in sources:
        result = await src.get_quote(ticker)
        if result:
            return {"country": country, "source": src.name, "quote": result}
    return {"country": country, "quote": None}


@app.get("/api/history/{ticker}")
async def history(
    ticker: str,
    period: str = Query(default="1mo"),
    country: CountryCode = Depends(country_dependency),
) -> dict:
    sources = [s for s in get_sources_by_name(price_sources_for(country))
               if isinstance(s, PriceSource)]
    for src in sources:
        points = await src.get_history(ticker, period=period)
        if points:
            return {"country": country, "source": src.name, "points": points}
    return {"country": country, "points": []}


@app.get("/api/macro")
async def macro(country: CountryCode = Depends(country_dependency)) -> dict:
    sources = [s for s in get_sources_by_name(macro_sources_for(country))
               if isinstance(s, MacroSource)]
    results = await asyncio.gather(
        *(s.get_indicators(country) for s in sources),
        return_exceptions=True,
    )
    points: list = []
    for res in results:
        if isinstance(res, list):
            points.extend(res)
    return {"country": country, "count": len(points), "indicators": points}


@app.get("/api/funds/search")
async def funds_search(
    query: str = Query(..., min_length=2),
    country: CountryCode = Depends(country_dependency),
) -> dict:
    sources = [s for s in get_sources_by_name(funds_sources_for(country))
               if isinstance(s, FundSource)]
    if not sources:
        return {"country": country, "funds": [], "note": "fund search not available for this country"}
    results: list = []
    for src in sources:
        results.extend(await src.search(query))
    return {"country": country, "count": len(results), "funds": results}


# ---------- Companies (top-30 per country + detail) -----------------------

@app.get("/api/companies")
async def companies_list(
    country: CountryCode = Depends(country_dependency),
    limit: int = Query(default=30, ge=1, le=50),
) -> dict:
    """Top-N companies for the country. Names + sectors only — fast index."""
    if country == "GLOBAL":
        country = settings.DEFAULT_COUNTRY  # type: ignore[assignment]
    return {"country": country,
             "items": list_companies(country=country, limit=limit)}


@app.get("/api/companies/{ticker}")
async def company_detail(
    ticker: str,
    country: CountryCode = Depends(country_dependency),
) -> dict:
    """10y price chart + key fundamentals + recent news for one company."""
    profile = await get_company_profile(ticker)
    if profile is None:
        return {"country": country, "ticker": ticker, "profile": None,
                 "error": "no_data"}
    return {"country": country, "ticker": ticker, "profile": profile}


# ---------- Briefings (scenario + brief + news in one shot) ---------------

@app.get("/api/briefings")
async def briefings(
    country: CountryCode = Depends(country_dependency),
    limit: int = Query(default=24, ge=4, le=60),
) -> dict:
    """One-shot briefings payload for the magazine page. Fuses:
      - cached scenario snapshot (events + market regime + policy)
      - live news from the country's news sources (last `limit` items)

    The frontend groups items by `topic` (Scenario / Wars / Macro / AI &
    Tech / Policy / Markets) using simple keyword classification.
    """
    snap = scenario_store.get(country)
    sources = [s for s in get_sources_by_name(news_sources_for(country))
               if isinstance(s, NewsSource)]
    results = await asyncio.gather(
        *(s.fetch_news(country=country, limit=limit) for s in sources),
        return_exceptions=True,
    )
    items: list = []
    for res in results:
        if isinstance(res, list):
            items.extend(res)
    items.sort(key=lambda x: x.published_at, reverse=True)
    # de-duplicate by URL/title
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped = []
    for it in items:
        key_url = (it.url or "").strip()
        key_title = (it.title or "").strip().lower()
        if key_url and key_url in seen_urls:
            continue
        if key_title and key_title in seen_titles:
            continue
        if key_url:
            seen_urls.add(key_url)
        if key_title:
            seen_titles.add(key_title)
        deduped.append(it)
    # tag each item with a topic
    tagged = [_tag_briefing(it) for it in deduped[:limit]]
    return {
        "country": country,
        "scenario": snap,
        "items": tagged,
    }


_TOPIC_KEYWORDS = {
    "Wars & Geopolitics": ["war", "ukraine", "russia", "israel", "gaza",
                              "iran", "houthi", "taiwan", "china us",
                              "sanction", "ceasefire", "conflict"],
    "AI & Tech": ["ai ", " ai,", "artificial intelligence", "nvidia",
                   "openai", "chatgpt", "anthropic", "semiconductor",
                   "data center", "chip"],
    "Policy & Rates": ["rbi", "federal reserve", "fed ", "ecb", "boe",
                        "rate cut", "rate hike", "monetary policy",
                        "inflation", "cpi", "repo rate", "budget", "tariff"],
    "Markets": ["nifty", "sensex", "s&p", "dow", "nasdaq", "ftse",
                 "earnings", "ipo", "buyback", "dividend"],
    "Macro": ["gdp", "growth", "unemployment", "recession", "trade deficit",
               "current account", "imf", "world bank", "oil price"],
}


def _tag_briefing(item) -> dict:
    """Return the news item as a plain dict with a `topic` tag."""
    haystack = f"{item.title} {item.summary or ''}".lower()
    topic = "Markets"
    for label, kws in _TOPIC_KEYWORDS.items():
        if any(kw in haystack for kw in kws):
            topic = label
            break
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "published_at": item.published_at.isoformat(),
        "summary": item.summary,
        "sentiment_score": item.sentiment_score,
        "sentiment_label": item.sentiment_label,
        "tickers": item.tickers,
        "topic": topic,
    }


# ---------- Answer (dashboard-shaped payload for /answer page) ------------

class AnswerRequest(BaseModel):
    """Same shape as AskRequest but POST-only for clarity at the route boundary."""
    query: str = Field(..., min_length=1, max_length=500)
    instrument_type: InstrumentType | None = None
    amount: float | None = Field(default=None, ge=0)
    horizon_years: int | None = Field(default=None, ge=0, le=50)
    risk_tolerance: RiskLevel | None = None
    goal: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    income_bracket: str | None = None
    income: float | None = Field(default=None, ge=0)


@app.post("/api/answer")
async def answer(
    body: AnswerRequest,
    response: Response,
    country: CountryCode = Depends(country_dependency),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> dict:
    """Dashboard-shaped result for the /answer page.

    Internally runs the same orchestrator as /api/ask, then re-packages the
    envelope into named *panels* the dashboard renders directly:

      - profile        : the user inputs the page captured (income, monthly amount, etc.)
      - allocation     : suggested split (Net Worth panel)
      - projection     : SIP future value + Monte Carlo range (Budget Status panel)
      - fund_candidates: ranked picks (Recent Transactions table)
      - videos         : YouTube embeds (Spending This Month panel)
      - articles       : reading list (Income vs Expenses panel)
      - crowd          : 'what beginners do' items (Accounts panel)
      - scenario       : current backdrop callout
      - intent         : classified intent
      - envelope       : the full ResponseEnvelope (for fallback rendering)
    """
    user_id = x_user_id or str(uuid.uuid4())
    session_id = x_session_id or str(uuid.uuid4())
    response.headers["X-User-Id"] = user_id
    response.headers["X-Session-Id"] = session_id

    user = UserContext(
        country=country,
        instrument_type=body.instrument_type,
        amount=body.amount,
        horizon_years=body.horizon_years,
        risk_tolerance=body.risk_tolerance,
        goal=body.goal,
        age=body.age,
        income_bracket=body.income_bracket,
    )
    # Run answer-mode classifier alongside the orchestrator. Both are async
    # so they can overlap — the orchestrator is the heavier of the two.
    mode_task = asyncio.create_task(classify_answer_mode(body.query))
    envelope = await orchestrator_ask(body.query, user, user_id=user_id,
                                         session_id=session_id)
    try:
        answer_mode = await mode_task
    except Exception:
        answer_mode = "analysis"
    panels = _panels_from_envelope(envelope, user, body.income)
    return {
        "intent": envelope.intent.value,
        "answer_mode": answer_mode,
        "query": envelope.query,
        "country": country,
        "generated_at": envelope.generated_at.isoformat(),
        "disclaimer": envelope.disclaimer,
        "panels": panels,
        "envelope": envelope.model_dump(mode="json"),
    }


def _panels_from_envelope(envelope: ResponseEnvelope, user: UserContext,
                            income: float | None) -> dict:
    """Slice the typed blocks into the dashboard layout."""
    panels: dict[str, Any] = {
        "profile": {
            "income": income,
            "amount": user.amount,
            "horizon_years": user.horizon_years,
            "risk_tolerance": (user.risk_tolerance.value
                                 if user.risk_tolerance else None),
            "age": user.age,
            "income_bracket": user.income_bracket,
        },
        "callouts": [],
        "form": None,
        "allocation": None,
        "projection_point": None,
        "projection_range": None,
        "fund_candidates": [],
        "tilts": [],
        "videos": [],
        "articles": [],
        "crowd": [],
        "winner_table": None,
        "narratives": [],
        "citations": [],
        "history": None,
    }
    for block in envelope.blocks:
        b = block.model_dump()
        kind = b.get("kind")
        if kind == "form":
            panels["form"] = b
        elif kind == "callout":
            panels["callouts"].append(b)
        elif kind == "narrative":
            panels["narratives"].append(b)
        elif kind == "video":
            panels["videos"].extend(b.get("items") or [])
        elif kind == "citations":
            panels["citations"] = b.get("sources") or []
        elif kind == "table":
            title = (b.get("title") or "").lower()
            if "candidate" in title:
                panels["fund_candidates"].append(b)
            elif "allocation" in title:
                panels["allocation"] = b
            elif "tilt" in title:
                panels["tilts"].append(b)
            elif "winner" in title:
                panels["winner_table"] = b
            elif "window stats" in title or "point projection" in title:
                panels["projection_point"] = b
            else:
                # generic table — bucket under narratives so it still renders
                panels.setdefault("tables", []).append(b)
        elif kind == "chart":
            title = (b.get("title") or "").lower()
            if "range lands" in title or "monte" in title:
                panels["projection_range"] = b
            elif "during" in title:
                panels["history"] = b
            else:
                panels.setdefault("charts", []).append(b)
        elif kind == "list":
            title = (b.get("title") or "").lower()
            items = b.get("items") or []
            if "beginners" in title or "across the country" in title:
                panels["crowd"] = items
            elif "video" in title:
                panels["videos"].extend(items)
            elif "today's brief" in title or "what affects" in title:
                panels.setdefault("lists", []).append(b)
            else:
                # heuristic: items with a `url` field → reading material
                if any(it.get("url") for it in items if isinstance(it, dict)):
                    panels["articles"].extend(items)
                else:
                    panels.setdefault("lists", []).append(b)
    return panels
