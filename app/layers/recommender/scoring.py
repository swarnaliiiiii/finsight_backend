"""Score and compare instrument candidates on factors beginners care about.

Higher score = better choice for the user's context. Scoring is rule-based and
transparent — every score has a reason the agent can quote back to the user.
"""
from __future__ import annotations

from app.schemas import (Comparison, InstrumentCandidate, InstrumentType,
                                  UserContext)

_DEFAULT_WEIGHTS: dict[str, float] = {
    "returns_3y": 0.30,
    "returns_5y": 0.20,
    "expense_ratio": 0.20,
    "aum_crore": 0.10,
    "risk_match": 0.10,
    "consensus_rank": 0.10,
}


def score_candidates(candidates: list[InstrumentCandidate],
                     user: UserContext) -> list[InstrumentCandidate]:
    """Annotate each candidate with a `_score` attribute and return sorted desc."""
    if not candidates:
        return []
    scored: list[tuple[float, InstrumentCandidate]] = []
    for c in candidates:
        score = _score_one(c, user)
        scored.append((score, c))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in scored]


def _score_one(c: InstrumentCandidate, user: UserContext) -> float:
    total = 0.0
    total += _normalize(c.returns_3y, 0, 25) * _DEFAULT_WEIGHTS["returns_3y"]
    total += _normalize(c.returns_5y, 0, 25) * _DEFAULT_WEIGHTS["returns_5y"]
    total += _inverse_normalize(c.expense_ratio, 0, 3) * _DEFAULT_WEIGHTS["expense_ratio"]
    total += _normalize(c.aum_crore, 0, 50000) * _DEFAULT_WEIGHTS["aum_crore"]
    total += _risk_match_score(c, user) * _DEFAULT_WEIGHTS["risk_match"]
    if c.consensus_rank:
        total += max(0.0, 1.0 - (c.consensus_rank - 1) * 0.1) * _DEFAULT_WEIGHTS["consensus_rank"]
    return round(total * 100, 1)


def _normalize(value: float | None, lo: float, hi: float) -> float:
    if value is None:
        return 0.5
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _inverse_normalize(value: float | None, lo: float, hi: float) -> float:
    if value is None:
        return 0.5
    return 1.0 - _normalize(value, lo, hi)


def _risk_match_score(c: InstrumentCandidate, user: UserContext) -> float:
    if not user.risk_tolerance or not c.risk_level:
        return 0.5
    order = ["low", "moderate", "high", "very_high"]
    try:
        diff = abs(order.index(c.risk_level.value) - order.index(user.risk_tolerance.value))
    except ValueError:
        return 0.5
    return max(0.0, 1.0 - diff * 0.33)


def compare_candidates(candidates: list[InstrumentCandidate]) -> Comparison:
    """Build a side-by-side comparison with winners per factor."""
    if not candidates:
        return Comparison(candidates=[], factors=[], winner_by_factor={},
                           summary="No candidates to compare.")
    factors = ["returns_3y", "returns_5y", "expense_ratio", "aum_crore", "consensus_rank"]
    winners: dict[str, str] = {}
    for factor in factors:
        winner = _winner_for(candidates, factor)
        if winner:
            winners[factor] = winner.name
    summary = _build_summary(candidates, winners)
    return Comparison(candidates=candidates, factors=factors,
                       winner_by_factor=winners, summary=summary)


def _winner_for(candidates: list[InstrumentCandidate],
                 factor: str) -> InstrumentCandidate | None:
    valid = [c for c in candidates if getattr(c, factor, None) is not None]
    if not valid:
        return None
    if factor in ("expense_ratio", "consensus_rank"):
        return min(valid, key=lambda c: getattr(c, factor))
    return max(valid, key=lambda c: getattr(c, factor))


def _build_summary(candidates: list[InstrumentCandidate],
                    winners: dict[str, str]) -> str:
    lines = [f"Comparing {len(candidates)} options:"]
    for factor, name in winners.items():
        readable = factor.replace("_", " ").title()
        lines.append(f"  - Best {readable}: {name}")
    return "\n".join(lines)
