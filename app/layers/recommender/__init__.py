"""Recommender layer: deterministic scoring, ranking, comparison + the
consensus + enrichment helpers that feed candidates into the scorer.

No LLM calls. No agent imports. Pure rule-based ranking + I/O for fetching
candidate fund/stock lists.
"""
from app.layers.recommender.consensus import consensus_fetcher
from app.layers.recommender.curated import curated_candidates
from app.layers.recommender.enrichment import enrich
from app.layers.recommender.scoring import compare_candidates, score_candidates

__all__ = ["compare_candidates", "consensus_fetcher", "curated_candidates",
           "enrich", "score_candidates"]
