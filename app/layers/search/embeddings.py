"""Embeddings adapter.

Provider is selected by `settings.GEMINI_API_KEY` for v1. Returns a fixed-
dimension vector for one or more strings. Soft-disabled (returns empty list
of vectors) when no key is configured — callers should check.

Swapping to a different provider means changing this one module.
"""
from __future__ import annotations

import logging
from typing import Sequence

from app.config import settings

logger = logging.getLogger(__name__)

# Gemini embeddings. `gemini-embedding-001` is the v1 model name; the
# older `text-embedding-004` is deprecated. Both return 768-d.
_EMBEDDING_DIM = 768
_MODEL = "models/gemini-embedding-001"


def is_available() -> bool:
    return bool(settings.GEMINI_API_KEY)


def dim() -> int:
    return _EMBEDDING_DIM


async def embed(texts: Sequence[str]) -> list[list[float]]:
    """Return one vector per input string, or an empty list per item if the
    provider isn't configured / failed."""
    if not texts:
        return []
    if not settings.GEMINI_API_KEY:
        return [[] for _ in texts]
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError:
        logger.debug("langchain_google_genai not installed; embeddings disabled")
        return [[] for _ in texts]
    try:
        client = GoogleGenerativeAIEmbeddings(
            model=_MODEL, google_api_key=settings.GEMINI_API_KEY,
        )
        vectors = await client.aembed_documents(list(texts))
        return [list(v) for v in vectors]
    except Exception:
        logger.exception("embeddings provider failed")
        return [[] for _ in texts]
