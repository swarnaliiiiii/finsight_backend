"""Monte Carlo for SIP outcomes.

Samples annual return per year from a normal distribution (mu, sigma), runs
N simulations, and returns p10/p50/p90 of final value. This is intentionally
simple — the agent's job is to frame it for beginners, not run a textbook
risk model.

We do not use a fat-tailed distribution; equity returns are not normal but
the percentiles we surface (p10/p50/p90) survive the simplification well
enough at the beginner-education level. Adopting Student-t or empirical
bootstrap is a later refinement.
"""
from __future__ import annotations

import random
from statistics import quantiles

from app.schemas import ProjectionRange

# Conservative defaults — sigma based on long-run Indian equity (~16%
# annualized). The orchestrator may override per-category later.
_DEFAULT_MU = 0.12
_DEFAULT_SIGMA = 0.16


def monte_carlo_sip(monthly_amount: float, years: float,
                     mu: float = _DEFAULT_MU,
                     sigma: float = _DEFAULT_SIGMA,
                     n_simulations: int = 1000,
                     seed: int | None = None) -> ProjectionRange:
    rng = random.Random(seed)
    months = int(round(years * 12))
    finals: list[float] = []
    for _ in range(n_simulations):
        balance = 0.0
        # Use yearly samples of return; apply same monthly rate within each year.
        for year in range(int(years)):
            annual = rng.gauss(mu, sigma)
            monthly = annual / 12.0
            for _m in range(12):
                balance = (balance + monthly_amount) * (1 + monthly)
        # Handle fractional-year remainder if `years` is non-integer.
        leftover_months = months - int(years) * 12
        if leftover_months:
            annual = rng.gauss(mu, sigma)
            monthly = annual / 12.0
            for _m in range(leftover_months):
                balance = (balance + monthly_amount) * (1 + monthly)
        finals.append(balance)
    finals.sort()
    p10, p50, p90 = _percentiles(finals, (10, 50, 90))
    return ProjectionRange(
        invested_total=round(monthly_amount * months, 2),
        monthly_amount=monthly_amount,
        months=months,
        annual_return_mean=mu,
        annual_return_stdev=sigma,
        p10=round(p10, 2),
        p50=round(p50, 2),
        p90=round(p90, 2),
        n_simulations=n_simulations,
    )


def _percentiles(sorted_xs: list[float], pcts: tuple[int, ...]) -> tuple[float, ...]:
    if not sorted_xs:
        return tuple(0.0 for _ in pcts)
    out: list[float] = []
    n = len(sorted_xs)
    for p in pcts:
        idx = max(0, min(n - 1, int(round(p / 100.0 * (n - 1)))))
        out.append(sorted_xs[idx])
    return tuple(out)
