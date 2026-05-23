"""Vector-store ORM. Lives in the memory layer because it shares the engine,
session factory, and DB lifecycle.

Storage strategy:
  - Embedding stored as a BLOB (length-prefixed float32 array) for portability.
  - Postgres can later move to pgvector via a column-type swap; the schema
    stays the same shape from the application's POV.
  - Cosine similarity is computed in Python at query time (brute force).
    Fine up to ~10k chunks; swap in pgvector / FAISS once the corpus grows.
"""
from __future__ import annotations

import struct
from datetime import datetime, timezone

from sqlalchemy import (DateTime, Index, Integer, LargeBinary, String, Text,
                          func)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.layers.memory.models import Base

# BigInteger().with_variant(Integer(), "sqlite") for portable PK.
from sqlalchemy import BigInteger
_BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentChunk(Base):
    """One embeddable chunk of a source document."""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True,
                                       autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False,
                                            index=True)  # 'sebi' | 'amc' | ...
    doc_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # length-prefixed float32 array. None means "indexed without embeddings yet".
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        server_default=func.now())

    __table_args__ = (
        Index("ix_document_chunks_source_doc", "source", "doc_id"),
    )


# --- BLOB helpers ---------------------------------------------------------

def pack_vector(v: list[float]) -> bytes:
    return struct.pack(f"<{len(v)}f", *v)


def unpack_vector(b: bytes, dim: int) -> list[float]:
    if not b:
        return []
    return list(struct.unpack(f"<{dim}f", b[:4 * dim]))
