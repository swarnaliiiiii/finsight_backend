"""Deterministic analytics over a price series for an era window.

Inputs: a ticker, the source-provided list of `PricePoint`s, and an Era.
Output: an EraPerformance with start/end price, period return, max
drawdown, and annualized volatility computed strictly over the window.

No I/O here — the caller (layer-call wrapper) fetches the series; this
module is pure math. Skips gracefully when the series doesn't cover the
window.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

from app.layers.market_data.base import PricePoint
from app.schemas import Era, EraPerformance


def compute_era_performance(ticker: str, era: Era,
                              points: list[PricePoint]) -> EraPerformance:
    """Compute window stats. Returns nulls for fields we can't fill."""
    in_window = _filter_window(points, era.start_date, era.end_date)
    if not in_window:
        return EraPerformance(
            ticker=ticker,
            era_id=era.id,
            start_price=None,
            end_price=None,
            period_return_pct=None,
            max_drawdown_pct=None,
            annualized_volatility_pct=None,
            notes=["no price data inside the era window for this ticker"],
        )

    start_price = in_window[0].close
    end_price = in_window[-1].close
    period_return = ((end_price / start_price) - 1) * 100 if start_price else None
    max_dd = _max_drawdown([p.close for p in in_window])
    vol = _annualized_volatility([p.close for p in in_window])
    summary_points = _downsample(in_window, max_points=80)

    notes: list[str] = []
    if len(in_window) < 10:
        notes.append("series is sparse — stats may be noisy")
    return EraPerformance(
        ticker=ticker,
        era_id=era.id,
        start_price=round(start_price, 4) if start_price is not None else None,
        end_price=round(end_price, 4) if end_price is not None else None,
        period_return_pct=(round(period_return, 2)
                            if period_return is not None else None),
        max_drawdown_pct=round(max_dd, 2) if max_dd is not None else None,
        annualized_volatility_pct=(round(vol, 2) if vol is not None else None),
        points=summary_points,
        notes=notes,
    )


# --- pure helpers ---------------------------------------------------------

def _filter_window(points: list[PricePoint], start: date,
                    end: date) -> list[PricePoint]:
    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)
    out = [p for p in points if _utc(p.timestamp) >= start_dt
            and _utc(p.timestamp) <= end_dt]
    out.sort(key=lambda p: p.timestamp)
    return out


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _max_drawdown(closes: list[float]) -> float | None:
    if not closes:
        return None
    peak = closes[0]
    max_dd = 0.0
    for px in closes:
        if px > peak:
            peak = px
        if peak > 0:
            dd = (px / peak - 1) * 100
            if dd < max_dd:
                max_dd = dd
    return max_dd


def _annualized_volatility(closes: list[float]) -> float | None:
    if len(closes) < 2:
        return None
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))
             if closes[i - 1] > 0]
    if not rets:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    daily = math.sqrt(var)
    # Assume daily samples; standard ~252 trading days.
    return daily * math.sqrt(252) * 100


def _downsample(points: list[PricePoint], *, max_points: int) -> list[dict]:
    if len(points) <= max_points:
        return [_to_point_dict(p) for p in points]
    step = len(points) // max_points
    return [_to_point_dict(p) for p in points[::step]]


def _to_point_dict(p: PricePoint) -> dict:
    return {
        "t": p.timestamp.isoformat() if isinstance(p.timestamp, datetime)
              else str(p.timestamp),
        "close": p.close,
    }
