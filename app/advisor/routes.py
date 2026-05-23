"""Web-app facing endpoints for the Advisor Agent."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.advisor.agent import run_advisor
from app.layers.education import explain
from app.layers.recommender import (compare_candidates, consensus_fetcher,
                                       enrich)
from app.schemas import (Comparison, InstrumentType, Recommendation, RiskLevel,
                          UserContext)
from app.core.geography import CountryCode, country_dependency

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.post("/recommend", response_model=Recommendation)
async def recommend(
    instrument_type: InstrumentType,
    amount: float | None = Query(default=None, ge=0),
    horizon_years: int | None = Query(default=None, ge=0, le=50),
    risk_tolerance: RiskLevel | None = Query(default=None),
    goal: str | None = Query(default=None),
    age: int | None = Query(default=None, ge=0, le=120),
    country: CountryCode = Depends(country_dependency),
) -> Recommendation:
    """Main entry: user describes what they want, agent returns top picks +
    reasoning + education module. Beginner-friendly."""
    user = UserContext(
        instrument_type=instrument_type,
        country=country,
        amount=amount,
        horizon_years=horizon_years,
        risk_tolerance=risk_tolerance,
        goal=goal,
        age=age,
    )
    return await run_advisor(user)


@router.get("/compare")
async def compare(
    instrument_type: InstrumentType,
    category: str | None = Query(default=None),
    country: CountryCode = Depends(country_dependency),
) -> Comparison:
    """Returns a side-by-side comparison of the top 5-6 candidates for an
    instrument type. Used by the Compare screen on the web app."""
    candidates = await consensus_fetcher.fetch(
        instrument_type=instrument_type, country=country, category=category)
    candidates = candidates[:6]
    enriched = await enrich(candidates, country)
    return compare_candidates(enriched)


@router.get("/explain/{term}")
async def explain_term(
    term: str,
    country: CountryCode = Depends(country_dependency),
):
    """Beginner-friendly explanation of a financial term with current values
    of the entities that affect it."""
    result = await explain(term, country=country)
    if not result:
        raise HTTPException(status_code=404,
                              detail=f"No explanation available for '{term}'.")
    return result
