"""FinSight AI backend entrypoint.

All routes accept an `X-Country-Code` header (IN/US/UK). Mobile clients resolve
the device's geolocation on-device and send the ISO country code. This drives
which data sources are queried.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.advisor.routes import router as advisor_router
from app.brief.routes import router as brief_router
from app.core.geography import (CountryCode, country_dependency, funds_sources_for,
                                 macro_sources_for, market_locale, news_sources_for,
                                 price_sources_for)
from app.layers.market_data import get_sources_by_name
from app.layers.market_data.base import (FundSource, MacroSource, NewsSource,
                                            PriceSource)
from app.layers.memory import close_memory, init_memory
from app.layers.scenario import (scenario_store, start_scenario_refresher,
                                    stop_scenario_refresher)
from app.layers.search import vector_ingest
from app.orchestrator import ask as orchestrator_ask
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
