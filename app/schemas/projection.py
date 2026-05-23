"""Projection schemas: results of the Projection/Quant layer.

All values are denominated in the user's currency (the layer doesn't convert;
it just computes). The agent reads these and writes plain-English framing.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Projection(BaseModel, frozen=True):
    """Single deterministic projection (point estimate)."""
    kind: str  # "sip_future_value" | "lump_sum" | "required_sip"
    invested_total: float
    final_value: float
    annual_return_assumed: float
    months: int
    monthly_amount: float | None = None
    lump_sum_amount: float | None = None
    growth_multiple: float = 0.0
    notes: list[str] = Field(default_factory=list)


class ProjectionRange(BaseModel, frozen=True):
    """Range of outcomes from a Monte Carlo simulation. p10/p50/p90 are the
    10th / 50th / 90th percentile final values."""
    kind: str = "monte_carlo"
    invested_total: float
    monthly_amount: float
    months: int
    annual_return_mean: float
    annual_return_stdev: float
    p10: float
    p50: float
    p90: float
    n_simulations: int = 1000


class AllocationSlice(BaseModel, frozen=True):
    bucket: str  # "equity_sip" | "debt_fund" | "gold" | "emergency_cash"
    pct: float
    rationale: str


class AllocationPlan(BaseModel, frozen=True):
    """Rule-based split of a target amount across instrument buckets."""
    target_monthly: float | None = None
    target_lump_sum: float | None = None
    slices: list[AllocationSlice]
    method: str  # short tag for the rule used: "age_120_minus" | "risk_bucket"
    assumptions: list[str] = Field(default_factory=list)
