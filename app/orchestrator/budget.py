"""Per-query budget enforcement.

Every plan step decrements a counter. When a counter hits zero, the runner
returns what it has and tags the result `budget_exhausted=True`. This is the
cost/latency safety net — no query can fan out unboundedly.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(Exception):
    """Raised by a layer/agent step when the relevant budget hits zero."""


@dataclass
class QueryBudget:
    # Tuned for INSTRUMENT_STARTER (the largest plan: ~10 layer calls + 4
    # agents). Other plans run well under the cap.
    max_layer_calls: int = 14
    max_agent_invocations: int = 8
    max_search_queries: int = 3
    max_llm_tokens: int = 30_000

    used_layer_calls: int = 0
    used_agent_invocations: int = 0
    used_search_queries: int = 0
    used_llm_tokens: int = 0

    notes: list[str] = field(default_factory=list)

    def spend_layer_call(self, name: str) -> None:
        if self.used_layer_calls >= self.max_layer_calls:
            raise BudgetExceeded(f"layer-call budget exhausted at '{name}'")
        self.used_layer_calls += 1

    def spend_agent_invocation(self, name: str) -> None:
        if self.used_agent_invocations >= self.max_agent_invocations:
            raise BudgetExceeded(f"agent-invocation budget exhausted at '{name}'")
        self.used_agent_invocations += 1

    def spend_search(self) -> None:
        if self.used_search_queries >= self.max_search_queries:
            raise BudgetExceeded("search-query budget exhausted")
        self.used_search_queries += 1

    def spend_llm_tokens(self, count: int) -> None:
        self.used_llm_tokens += count
        if self.used_llm_tokens > self.max_llm_tokens:
            raise BudgetExceeded("LLM-token budget exhausted")

    def note(self, message: str) -> None:
        self.notes.append(message)

    def as_dict(self) -> dict:
        return {
            "layer_calls": f"{self.used_layer_calls}/{self.max_layer_calls}",
            "agent_invocations": f"{self.used_agent_invocations}/{self.max_agent_invocations}",
            "search_queries": f"{self.used_search_queries}/{self.max_search_queries}",
            "llm_tokens": f"{self.used_llm_tokens}/{self.max_llm_tokens}",
            "notes": self.notes,
        }
