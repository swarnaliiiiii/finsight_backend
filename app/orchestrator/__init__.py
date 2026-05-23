"""Master Orchestrator: the only module allowed to compose layers + agents.

Owns:
  - Intent -> plan mapping (planner.INTENT_PLANS)
  - Per-query budget enforcement (budget.QueryBudget)
  - Layer calls (layer_calls.LAYER_CALLS)
  - Agent fan-out (runner.AGENT_REGISTRY)

Agents never call each other. Agents never call layers. The orchestrator runs
the deterministic plan picked by the Intent agent and assembles the result.
"""
from app.orchestrator.budget import BudgetExceeded, QueryBudget
from app.orchestrator.runner import ask

__all__ = ["BudgetExceeded", "QueryBudget", "ask"]
