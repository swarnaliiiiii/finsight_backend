"""SIP / lump-sum / goal-amount math.

All formulas use a monthly compounding model: annual return r is converted
to monthly r/12. We use the "annuity due" form (contribution at the start
of the month) which matches how SIPs are usually marketed.
"""
from __future__ import annotations

from app.schemas import Projection


def sip_future_value(monthly_amount: float, annual_return: float,
                      years: float) -> Projection:
    """Future value of a monthly SIP.

    Formula: M * ((1+i)^n - 1) / i * (1+i)
    where M = monthly amount, i = annual_return/12, n = years*12.
    Annuity-due (contribution at start of month).
    """
    months = int(round(years * 12))
    i = annual_return / 12.0
    if i == 0:
        final = monthly_amount * months
    else:
        final = monthly_amount * (((1 + i) ** months - 1) / i) * (1 + i)
    invested = monthly_amount * months
    growth = (final / invested) if invested else 0.0
    return Projection(
        kind="sip_future_value",
        invested_total=round(invested, 2),
        final_value=round(final, 2),
        annual_return_assumed=annual_return,
        months=months,
        monthly_amount=monthly_amount,
        growth_multiple=round(growth, 3),
    )


def lump_sum_future_value(amount: float, annual_return: float,
                            years: float) -> Projection:
    """Future value of a single lump-sum investment compounded annually."""
    final = amount * ((1 + annual_return) ** years)
    months = int(round(years * 12))
    return Projection(
        kind="lump_sum",
        invested_total=round(amount, 2),
        final_value=round(final, 2),
        annual_return_assumed=annual_return,
        months=months,
        lump_sum_amount=amount,
        growth_multiple=round(final / amount, 3) if amount else 0.0,
    )


def required_sip_for_goal(goal_amount: float, annual_return: float,
                            years: float) -> Projection:
    """Inverse of sip_future_value: what monthly amount reaches the goal?"""
    months = int(round(years * 12))
    i = annual_return / 12.0
    if i == 0:
        monthly = goal_amount / months
    else:
        denom = (((1 + i) ** months - 1) / i) * (1 + i)
        monthly = goal_amount / denom
    invested = monthly * months
    return Projection(
        kind="required_sip",
        invested_total=round(invested, 2),
        final_value=round(goal_amount, 2),
        annual_return_assumed=annual_return,
        months=months,
        monthly_amount=round(monthly, 2),
        growth_multiple=round(goal_amount / invested, 3) if invested else 0.0,
    )
