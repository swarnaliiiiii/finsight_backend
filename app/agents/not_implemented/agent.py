"""Stub agent for intents whose plans haven't been built yet."""
from __future__ import annotations

from app.schemas import AgentInput, AgentOutput


async def run(input: AgentInput) -> AgentOutput:
    return AgentOutput(
        narrative=(
            "That kind of question is recognised but not yet handled by this "
            "build. Try asking 'what is a SIP', 'explain ETF', or 'what's "
            "the repo rate today'."),
        structured={"intent": input.intent.value, "status": "not_implemented"},
    )
