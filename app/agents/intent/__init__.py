"""Intent classification agent: NL query -> Intent enum.

Contract: `async def run(input: AgentInput) -> AgentOutput`. The classified
Intent goes into `AgentOutput.structured["intent"]`.
"""
from app.agents.intent.agent import run

__all__ = ["run"]
