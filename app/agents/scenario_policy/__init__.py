"""Current Scenario & Policy Impact agent.

Reads `input.scenario` (the cached snapshot from the Scenario layer) and
produces:
  - a beginner-safe narrative of the macro/geopolitical backdrop
  - `structured['tilts']`: dict[instrument_key -> 'tailwind' | 'neutral' |
    'headwind'] judging the current backdrop's effect on each instrument

The orchestrator's scenario_hook invokes this agent once per refresh cycle
to enrich the snapshot. Per-query plans (like CURRENT_NEWS) also invoke it
to frame fresh queries.
"""
from app.agents.scenario_policy.agent import run

__all__ = ["run"]
