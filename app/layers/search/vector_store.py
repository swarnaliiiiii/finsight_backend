"""Vector store backed by the memory layer's DB.

Two operations:
  - ingest(source, doc_id, title, text, ...) -> chunk + embed + persist
  - search(query, k=5, source=None)          -> top-k chunks by cosine

Chunking is paragraph-level with a 1000-char cap and no overlap. Plenty for
SEBI investor-protection PDFs (which are short paragraphs anyway) and AMC
factsheets. Tune later if needed.
"""
from __future__ import annotations

import logging
import math
from typing import Sequence

from sqlalchemy import select

from app.layers.memory.db import is_ready, session_scope
from app.layers.memory.vector_models import (DocumentChunk, pack_vector,
                                                 unpack_vector)
from app.layers.search.embeddings import dim as embedding_dim
from app.layers.search.embeddings import embed
from app.layers.search.embeddings import is_available as embeddings_available
from app.schemas import Document

logger = logging.getLogger(__name__)

_CHUNK_CHAR_CAP = 1000


# --- ingestion ------------------------------------------------------------

async def ingest(*, source: str, doc_id: str, title: str, text: str,
                   url: str | None = None,
                   metadata: dict | None = None) -> int:
    """Chunk, embed, and persist one document. Returns the number of chunks
    written. Idempotent in the sense that the same (source, doc_id) reruns
    will append duplicates — call delete first if you re-ingest."""
    if not is_ready():
        logger.debug("vector_store.ingest skipped: memory layer not ready")
        return 0
    chunks = _chunk(text)
    if not chunks:
        return 0
    if embeddings_available():
        vectors = await embed(chunks)
    else:
        vectors = [[] for _ in chunks]
    written = 0
    try:
        async with session_scope() as s:
            for i, (chunk_text, vec) in enumerate(zip(chunks, vectors)):
                packed = pack_vector(vec) if vec else None
                s.add(DocumentChunk(
                    source=source,
                    doc_id=doc_id,
                    title=title[:300],
                    url=url,
                    chunk_text=chunk_text,
                    chunk_index=i,
                    metadata_json=metadata or {},
                    embedding=packed,
                    embedding_dim=len(vec) if vec else None,
                ))
                written += 1
    except Exception:
        logger.exception("vector_store.ingest failed source=%s doc=%s",
                          source, doc_id)
        return 0
    return written


# --- retrieval ------------------------------------------------------------

async def search(query: str, *, k: int = 5,
                   source: str | None = None) -> list[Document]:
    """Return top-k chunks as Documents. Falls back to keyword scoring when
    no embeddings are available (or the query embeds to empty)."""
    if not is_ready() or not query.strip():
        return []
    vecs = await embed([query]) if embeddings_available() else [[]]
    qvec = vecs[0] if vecs else []
    try:
        async with session_scope() as s:
            stmt = select(DocumentChunk)
            if source is not None:
                stmt = stmt.where(DocumentChunk.source == source)
            rows = (await s.execute(stmt)).scalars().all()
    except Exception:
        logger.exception("vector_store.search failed")
        return []

    if qvec:
        scored = _rank_by_cosine(qvec, rows)
    else:
        scored = _rank_by_keyword(query.lower(), rows)
    return [_row_to_document(r, score) for score, r in scored[:k]]


def _rank_by_cosine(qvec: list[float],
                      rows: Sequence[DocumentChunk]) -> list[tuple[float, DocumentChunk]]:
    out: list[tuple[float, DocumentChunk]] = []
    qnorm = math.sqrt(sum(x * x for x in qvec))
    if qnorm == 0:
        return []
    for r in rows:
        if r.embedding is None or not r.embedding_dim:
            continue
        v = unpack_vector(r.embedding, r.embedding_dim)
        if not v:
            continue
        dot = sum(a * b for a, b in zip(qvec, v))
        vnorm = math.sqrt(sum(x * x for x in v))
        if vnorm == 0:
            continue
        score = dot / (qnorm * vnorm)
        out.append((score, r))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


def _rank_by_keyword(query_lc: str,
                       rows: Sequence[DocumentChunk]) -> list[tuple[float, DocumentChunk]]:
    tokens = [t for t in query_lc.split() if len(t) > 2]
    if not tokens:
        return []
    out: list[tuple[float, DocumentChunk]] = []
    for r in rows:
        body = r.chunk_text.lower()
        hits = sum(body.count(t) for t in tokens)
        if hits:
            out.append((float(hits), r))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


# --- helpers --------------------------------------------------------------

def _chunk(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= _CHUNK_CHAR_CAP:
            chunks.append(para)
            continue
        # Hard-split long paragraphs at the cap.
        start = 0
        while start < len(para):
            chunks.append(para[start:start + _CHUNK_CHAR_CAP])
            start += _CHUNK_CHAR_CAP
    return chunks


def _row_to_document(r: DocumentChunk, score: float) -> Document:
    return Document(
        id=f"chunk-{r.id}",
        title=r.title,
        url=r.url,
        snippet=r.chunk_text[:600],
        source=f"vector:{r.source}",
        kind="amc_doc" if r.source == "amc" else "sebi_doc"
                if r.source == "sebi" else "article",
        score=float(score),
    )
