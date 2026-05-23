"""Document: a retrieved piece of content the orchestrator hands to agents.

The Search/RAG layer produces these. Agents consume them as read-only inputs;
they cannot issue new searches.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Document(BaseModel, frozen=True):
    """One retrieved item: article, video, SEBI doc, AMC factsheet, etc."""
    id: str
    title: str
    url: str | None = None
    snippet: str
    source: str
    kind: str = "article"
    published_at: datetime | None = None
    score: float | None = None
