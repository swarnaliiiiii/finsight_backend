"""Rule-based allocation planner.

Combines two conventional heuristics:
  - Age-based equity tilt: equity% ≈ (120 − age), capped to [20, 80]
  - Risk-bucket override: low/moderate/high/very_high adjust by ±10-20pp

Beginners often see allocation as a single equity-vs-debt split. We split
further into equity-SIP / debt-fund / gold / emergency-cash to make the
plan actionable, but the splits remain rule-based and transparent.
"""
from __future__ import annotations

from app.schemas import AllocationPlan, AllocationSlice, RiskLevel

_RISK_TILT = {
    RiskLevel.LOW: -20,
    RiskLevel.MODERATE: -5,
    RiskLevel.HIGH: 10,
    RiskLevel.VERY_HIGH: 20,
}


def allocation_for_profile(*, age: int | None = None,
                            risk: RiskLevel | None = None,
                            target_monthly: float | None = None,
                            target_lump_sum: float | None = None,
                            ) -> AllocationPlan:
    """Compute equity / debt / gold / emergency split percentages.

    `age` drives the base; `risk` shifts it; the remainder is distributed
    across debt, gold, and an emergency-cash buffer.
    """
    equity = _equity_pct_for_age(age)
    equity = _apply_risk_tilt(equity, risk)
    equity = max(20, min(80, equity))

    remainder = 100 - equity
    # Conventional remainder split: 60% debt, 25% gold, 15% emergency cash.
    debt = round(remainder * 0.60)
    gold = round(remainder * 0.25)
    cash = remainder - debt - gold  # ensure exact 100 sum

    slices = [
        AllocationSlice(bucket="equity_sip", pct=float(equity),
                         rationale=_equity_rationale(age, risk)),
        AllocationSlice(bucket="debt_fund", pct=float(debt),
                         rationale="Stability + steadier yield; cushions equity drawdowns."),
        AllocationSlice(bucket="gold_etf", pct=float(gold),
                         rationale="Inflation + crisis hedge; small slice typically enough."),
        AllocationSlice(bucket="emergency_cash", pct=float(cash),
                         rationale="3-6 months expenses in liquid savings — invest only after this exists."),
    ]
    return AllocationPlan(
        target_monthly=target_monthly,
        target_lump_sum=target_lump_sum,
        slices=slices,
        method="age_120_minus + risk_tilt",
        assumptions=[
            "Equity% ≈ (120 − age) bounded to [20, 80], shifted by risk tolerance.",
            "Remainder split 60/25/15 across debt / gold / emergency-cash.",
            "Beginners should fund the emergency-cash bucket first.",
        ],
    )


def _equity_pct_for_age(age: int | None) -> int:
    if age is None:
        return 60  # default young-adult tilt
    return max(20, min(80, 120 - age))


def _apply_risk_tilt(equity: int, risk: RiskLevel | None) -> int:
    if risk is None:
        return equity
    return equity + _RISK_TILT.get(risk, 0)


def _equity_rationale(age: int | None, risk: RiskLevel | None) -> str:
    if risk == RiskLevel.LOW:
        return "Lower equity slice given low risk tolerance."
    if risk == RiskLevel.VERY_HIGH:
        return "Higher equity slice given a high risk appetite — expect bigger swings."
    if age is not None and age >= 55:
        return "Equity slice reduced as you approach the conventional retirement window."
    return "Conventional age-based equity tilt for long-horizon compounding."
