"""Idempotent schema creation — no Alembic for v1.

Postgres or SQLite both accept `metadata.create_all(checkfirst=True)`. When
the schema needs migrating, we'll bring in Alembic; until then this is
enough to bootstrap the memory layer at startup.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from app.layers.memory.models import Base
# Import vector_models so DocumentChunk is registered with Base.metadata.
from app.layers.memory import vector_models  # noqa: F401

logger = logging.getLogger(__name__)


async def create_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
    logger.info("memory: schema ensured (tables=%d)",
                 len(Base.metadata.tables))
