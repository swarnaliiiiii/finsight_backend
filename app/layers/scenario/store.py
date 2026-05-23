"""In-memory holder for per-country `CurrentScenario` snapshots.

Single asyncio process, so a plain dict is safe. `get` is sync (agents read
through the orchestrator on the request path). `set` is sync too — the
refresher is the only writer and runs in one task.
"""
from __future__ import annotations

from app.schemas import CurrentScenario


class _ScenarioStore:
    def __init__(self) -> None:
        self._snapshots: dict[str, CurrentScenario] = {}

    def get(self, country: str) -> CurrentScenario | None:
        """Return the latest snapshot for `country`, or None if not yet built."""
        return self._snapshots.get(country)

    def set(self, snapshot: CurrentScenario) -> None:
        self._snapshots[snapshot.country] = snapshot

    def known_countries(self) -> list[str]:
        return list(self._snapshots.keys())


scenario_store = _ScenarioStore()
