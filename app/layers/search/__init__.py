"""Search / RAG layer.

Three capabilities in this version:
  - web_search  : Tavily-backed general web retrieval
  - find_videos : YouTube Data API v3, soft-disabled without key
  - classify_event : LLM-graded event tagger (falls back to keyword rules)

Vector retrieval over SEBI / AMC docs is a future addition — it needs an
embedding backend + ingestion pipeline that deserves its own step.
"""
from app.layers.search.event_classifier import classify_event
from app.layers.search.vector_store import ingest as vector_ingest
from app.layers.search.vector_store import search as vector_search
from app.layers.search.web import web_search
from app.layers.search.youtube import find_videos

__all__ = ["classify_event", "find_videos", "vector_ingest",
            "vector_search", "web_search"]
