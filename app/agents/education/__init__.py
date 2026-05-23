"""Education agent: turns a structured Explanation (from the education
layer) into beginner-friendly narrative.

The layer does the lookup + live-data enrichment. The agent shapes the result
into 4-6 sentences a first-time investor can understand. Scenario-aware: if
the orchestrator passed a CurrentScenario, the narrative may briefly cite a
relevant tilt (e.g. "with the current rate environment...").
"""
from app.agents.education.agent import run

__all__ = ["run"]
