"""Projection / Quant layer.

Deterministic financial math: SIP future value, lump-sum growth, required
SIP for a goal amount, Monte Carlo range, allocation splits. No I/O, no LLM,
no user model.
"""
from app.layers.projection.allocation import allocation_for_profile
from app.layers.projection.monte_carlo import monte_carlo_sip
from app.layers.projection.sip import (lump_sum_future_value,
                                          required_sip_for_goal,
                                          sip_future_value)

__all__ = [
    "allocation_for_profile",
    "lump_sum_future_value",
    "monte_carlo_sip",
    "required_sip_for_goal",
    "sip_future_value",
]
