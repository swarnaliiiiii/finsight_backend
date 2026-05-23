"""Recommendation Reasoning agent: 'Why this fund stands out' narrative on
top of the Recommender layer's scored candidates.

Reads:
  - input.upstream['candidates']   : list[InstrumentCandidate]
  - input.upstream['comparison']   : Comparison | None (when COMPARE plan ran)
  - input.scenario                 : CurrentScenario | None

Writes:
  - narrative                       : 4-6 sentences explaining the top pick
  - structured                      : echoes candidates + top_pick_id +
                                       consensus_summary so Assembly can
                                       render a TableBlock
"""
from app.agents.recommendation.agent import run

__all__ = ["run"]
