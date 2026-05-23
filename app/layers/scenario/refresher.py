"""Background refresher: rebuilds the scenario snapshot for each supported
country every N hours, started from FastAPI's lifespan handler.

No separate worker process. One asyncio task lives inside the FastAPI app
process and exits cleanly on shutdown.

Optional `on_snapshot_built` callback lets the orchestrator enrich each
fresh snapshot (e.g. with LLM-graded instrument tilts) before it's stored.
The layer itself never imports an agent — it just receives a callable.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.layers.scenario.builder import build_scenario
from app.layers.scenario.store import scenario_store
from app.schemas import CurrentScenario

logger = logging.getLogger(__name__)

DEFAULT_REFRESH_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours
DEFAULT_COUNTRIES: tuple[str, ...] = ("IN", "US", "UK")

SnapshotEnricher = Callable[[CurrentScenario], Awaitable[CurrentScenario]]

_refresher_task: asyncio.Task | None = None


async def _refresh_loop(interval_seconds: int, countries: tuple[str, ...],
                          on_snapshot_built: SnapshotEnricher | None) -> None:
    """Forever loop: build snapshots for each country, optionally enrich,
    store them, sleep."""
    while True:
        for country in countries:
            try:
                snapshot = await build_scenario(country)
                if on_snapshot_built is not None:
                    try:
                        snapshot = await on_snapshot_built(snapshot)
                    except Exception:
                        logger.exception(
                            "scenario enricher failed country=%s; storing "
                            "snapshot without enrichment", country)
                scenario_store.set(snapshot)
                logger.info("scenario refreshed country=%s events=%d "
                             "headlines=%d tilts=%d",
                             country, len(snapshot.active_events),
                             len(snapshot.notable_headlines),
                             len(snapshot.instrument_tilts))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("scenario refresh failed country=%s", country)
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise


def start_scenario_refresher(
    interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
    countries: tuple[str, ...] = DEFAULT_COUNTRIES,
    on_snapshot_built: SnapshotEnricher | None = None,
) -> asyncio.Task:
    """Launch the refresher task. Safe to call once at app startup."""
    global _refresher_task
    if _refresher_task is not None and not _refresher_task.done():
        return _refresher_task
    _refresher_task = asyncio.create_task(
        _refresh_loop(interval_seconds, countries, on_snapshot_built),
        name="scenario-refresher",
    )
    logger.info("scenario refresher started interval=%ds countries=%s "
                 "enrich=%s", interval_seconds, countries,
                 on_snapshot_built is not None)
    return _refresher_task


async def stop_scenario_refresher() -> None:
    """Cancel the refresher and await its exit. Called from lifespan shutdown."""
    global _refresher_task
    if _refresher_task is None:
        return
    _refresher_task.cancel()
    try:
        await _refresher_task
    except (asyncio.CancelledError, Exception):
        pass
    _refresher_task = None
    logger.info("scenario refresher stopped")
