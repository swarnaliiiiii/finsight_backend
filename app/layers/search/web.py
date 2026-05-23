"""Tavily-backed web search returning typed `Document` results.

Tavily is the existing web search dependency (already wired in the
recommender's consensus.py). This module is the single owner of the API
going forward; other modules call through here.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.schemas import Document

_TAVILY_ENDPOINT = "https://api.tavily.com/search"

# Hosts that overwhelmingly serve video content. Used to mark Tavily hits
# as videos automatically (in addition to anything from youtube.find_videos).
_VIDEO_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "vimeo.com"}


async def web_search(query: str, *, country: str = "IN",
                      limit: int = 6) -> list[Document]:
    """General-purpose web search. Returns up to `limit` documents.
    Returns an empty list (no exception) if Tavily isn't configured.
    """
    if not settings.TAVILY_API_KEY:
        return []
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": min(limit, 10),
        "topic": "general",
        "include_answer": False,
    }
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
        try:
            r = await client.post(_TAVILY_ENDPOINT, json=payload)
            r.raise_for_status()
            results = r.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return []
    return [_to_document(res, country) for res in results[:limit]]


def _to_document(res: dict, country: str) -> Document:
    url = res.get("url") or ""
    host = urlparse(url).hostname or ""
    kind = "video" if host in _VIDEO_HOSTS else "article"
    published_at = _parse_dt(res.get("published_date"))
    return Document(
        id=_short_hash(url or res.get("title", "")),
        title=(res.get("title") or "")[:180],
        url=url or None,
        snippet=(res.get("content") or "")[:600],
        source="tavily-web",
        kind=kind,
        published_at=published_at,
        score=res.get("score"),
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


# Keep an importable async-gather convenience for parallel queries.
async def web_search_many(queries: list[str], *, country: str = "IN",
                            limit: int = 4) -> list[Document]:
    if not queries:
        return []
    results = await asyncio.gather(
        *(web_search(q, country=country, limit=limit) for q in queries),
        return_exceptions=True,
    )
    merged: list[Document] = []
    seen: set[str] = set()
    for r in results:
        if not isinstance(r, list):
            continue
        for d in r:
            key = (d.url or d.title).lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(d)
    return merged
