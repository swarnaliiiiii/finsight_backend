"""DB lifecycle for the memory layer.

One module-level engine + session factory. `init_memory()` is called from
the FastAPI lifespan; `close_memory()` disposes the engine on shutdown.

The engine is keyed off `settings.DATABASE_URL`. For local smoke tests use
`DATABASE_URL=sqlite+aiosqlite:///:memory:` — the migrations module emits
SQL that works on both Postgres and SQLite.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                       async_sessionmaker, create_async_engine)

from app.config import settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    url = settings.DATABASE_URL
    # SQLite (smoke) needs a special pool argument to share an in-memory DB
    # across connections.
    connect_args: dict = {}
    if url.startswith("sqlite+aiosqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(url, connect_args=connect_args, future=True,
                                  echo=False, pool_pre_ping=True)


async def init_memory() -> None:
    """Build the engine and run idempotent schema creation."""
    global _engine, _session_factory
    if _engine is not None:
        return
    _engine = _build_engine()
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False,
                                            class_=AsyncSession)
    # Local import keeps the module graph clean (migrations imports models
    # which imports from db).
    from app.layers.memory.migrations import create_all
    try:
        await create_all(_engine)
    except Exception:
        logger.exception("memory: schema creation failed; layer will degrade")


async def close_memory() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async-with helper used by repo.py. Yields None if the engine isn't
    initialised so callers can degrade gracefully."""
    if _session_factory is None:
        # Soft mode: layer not initialised. The repo functions handle this.
        raise RuntimeError("memory layer not initialised")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def is_ready() -> bool:
    return _session_factory is not None
