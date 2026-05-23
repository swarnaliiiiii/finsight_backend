"""Scenario layer: caches a `CurrentScenario` snapshot per country.

Owns:
  - `store`   : in-memory holder (sync read, async write)
  - `builder` : composes a snapshot from market_data + news layers
  - `refresher` : async background loop launched by FastAPI lifespan

Agents read snapshots via the orchestrator — they do NOT import this package
directly (enforced by .importlinter).
"""
from app.layers.scenario.builder import build_scenario
from app.layers.scenario.refresher import (start_scenario_refresher,
                                              stop_scenario_refresher)
from app.layers.scenario.store import scenario_store

__all__ = [
    "build_scenario",
    "scenario_store",
    "start_scenario_refresher",
    "stop_scenario_refresher",
]
