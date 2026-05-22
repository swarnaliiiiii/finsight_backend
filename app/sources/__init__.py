"""Data source adapters.

All sources expose async methods and return unified models from `base`.
The `registry` is the single entry point that geography routing uses.
"""
from app.sources.registry import get_source, get_sources_by_name  # noqa: F401
