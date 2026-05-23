"""Education layer: deterministic knowledge-graph lookup + live-data
enrichment for financial terms.

No LLM calls. The Education *agent* (later) wraps this layer with narrative
generation; the layer itself just returns structured Explanation objects.
"""
from app.layers.education.lookup import explain

__all__ = ["explain"]
