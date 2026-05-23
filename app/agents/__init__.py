"""LLM-driven reasoning agents.

Architectural rules (enforced by .importlinter):
  - No imports from `app.layers.*` (orchestrator owns I/O)
  - No imports from sibling agents (orchestrator owns fan-out)
  - May import from `app.schemas.*`

Each agent exposes exactly one async function:
    async def run(input: AgentInput) -> AgentOutput
"""
