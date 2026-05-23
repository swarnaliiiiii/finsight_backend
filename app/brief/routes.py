"""Daily Brief endpoint. In-memory cache (4h TTL) per country."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from cachetools import TTLCache

from app.brief.agent import run_brief
from app.schemas import DailyBrief
from app.core.geography import CountryCode, country_dependency

router = APIRouter(prefix="/api/brief", tags=["brief"])

# 4-hour cache keyed by country
_brief_cache: TTLCache = TTLCache(maxsize=10, ttl=4 * 60 * 60)


@router.get("/", response_model=DailyBrief)
async def get_brief(
    country: CountryCode = Depends(country_dependency),
    refresh: bool = Query(default=False, description="Bypass cache and regenerate."),
) -> DailyBrief:
    """Returns the Daily Brief for the user's country.

    3 educational action items + a one-line market summary, cached for 4 hours.
    """
    if not refresh and country in _brief_cache:
        return _brief_cache[country]
    brief = await run_brief(country)
    _brief_cache[country] = brief
    return brief
