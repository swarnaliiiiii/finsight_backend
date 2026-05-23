"""YouTube Data API v3 wrapper.

We don't have a heavyweight YouTube SDK dependency — a single GET to
`/youtube/v3/search` gives us what we need. Soft-disabled when
`YOUTUBE_API_KEY` is unset (returns []) so plans keep working in dev.

Quota: the search endpoint costs 100 units per call. Default daily quota is
10,000 = 100 calls/day. Cache aggressively if you wire this into hot paths.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

import httpx

from app.config import settings
from app.schemas import Document

_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"

_COUNTRY_REGION = {"IN": "IN", "US": "US", "UK": "GB"}


async def find_videos(query: str, *, country: str = "IN",
                       limit: int = 4) -> list[Document]:
    """Return up to `limit` beginner-friendly videos for `query`. Empty list
    if no API key is configured."""
    if not settings.YOUTUBE_API_KEY:
        return []
    params = {
        "key": settings.YOUTUBE_API_KEY,
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": min(limit, 10),
        "relevanceLanguage": "en",
        "safeSearch": "moderate",
        "regionCode": _COUNTRY_REGION.get(country, "US"),
        "videoEmbeddable": "true",
    }
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
        try:
            r = await client.get(_ENDPOINT, params=params)
            r.raise_for_status()
            items = r.json().get("items", [])
        except (httpx.HTTPError, ValueError):
            return []
    return [_to_document(it) for it in items[:limit]]


def _to_document(item: dict) -> Document:
    vid = item.get("id", {}).get("videoId") or ""
    sn = item.get("snippet", {}) or {}
    title = (sn.get("title") or "")[:180]
    channel = sn.get("channelTitle") or ""
    url = f"https://www.youtube.com/watch?v={vid}" if vid else None
    published_at = _parse_dt(sn.get("publishedAt"))
    snippet = (sn.get("description") or "")[:600]
    if channel:
        snippet = f"[{channel}] {snippet}"
    return Document(
        id=_short_hash(url or title),
        title=title,
        url=url,
        snippet=snippet,
        source="youtube",
        kind="video",
        published_at=published_at,
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
