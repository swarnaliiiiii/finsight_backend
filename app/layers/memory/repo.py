"""Memory repo: CRUD helpers exposed to the orchestrator.

All functions are best-effort: if the DB is unreachable or the layer isn't
initialised, we log and return a safe default (empty readout, no-op writes).
The orchestrator treats memory as a soft dependency so a transient outage
doesn't break the user-facing flow.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.layers.memory.db import is_ready, session_scope
from app.layers.memory.models import ActivityEvent, SessionTurn, UserProfile
from app.schemas import (Intent, InstrumentType, MemoryActivity, MemoryProfile,
                          MemoryReadout, MemorySessionTurn, RiskLevel)

logger = logging.getLogger(__name__)

# Hard caps on what we hand to agents — keep AgentInput small and bounded.
_RECENT_TURN_LIMIT = 5
_RECENT_ACTIVITY_LIMIT = 10


# --- profile --------------------------------------------------------------

async def get_or_create_profile(user_id: str, *, country: str = "IN"
                                  ) -> MemoryProfile:
    """Look up or create a profile. Always returns something usable, even if
    the DB call fails — falls back to an in-memory MemoryProfile."""
    fallback = MemoryProfile(user_id=user_id, country=country)
    if not is_ready():
        return fallback
    try:
        async with session_scope() as s:
            row = await s.get(UserProfile, user_id)
            if row is None:
                row = UserProfile(user_id=user_id, country=country)
                s.add(row)
                await s.flush()
            return _profile_from_row(row)
    except SQLAlchemyError:
        logger.exception("memory.get_or_create_profile failed user=%s", user_id)
        return fallback


async def update_profile(user_id: str, **fields: Any) -> MemoryProfile | None:
    """Merge non-None fields into the user's profile. Unknown keys are
    ignored. Returns the updated profile, or None on failure."""
    if not is_ready():
        return None
    allowed = {"country", "age", "risk_tolerance", "goal", "income_bracket",
                "comprehension_level", "instrument_type", "amount",
                "horizon_years"}
    updates: dict[str, Any] = {}
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "risk_tolerance" and isinstance(v, RiskLevel):
            updates[k] = v.value
        elif k == "instrument_type" and isinstance(v, InstrumentType):
            updates[k] = v.value
        else:
            updates[k] = v
    if not updates:
        return await get_or_create_profile(user_id)
    try:
        async with session_scope() as s:
            row = await s.get(UserProfile, user_id)
            if row is None:
                row = UserProfile(user_id=user_id, country=updates.get("country", "IN"))
                s.add(row)
            for k, v in updates.items():
                setattr(row, k, v)
            row.updated_at = datetime.now(timezone.utc)
            await s.flush()
            return _profile_from_row(row)
    except SQLAlchemyError:
        logger.exception("memory.update_profile failed user=%s", user_id)
        return None


# --- turns ----------------------------------------------------------------

async def record_turn(*, user_id: str, session_id: str, query: str,
                        intent: Intent, envelope: dict) -> None:
    """Persist one (query -> envelope) turn. Best-effort: failures don't
    propagate."""
    if not is_ready():
        return
    try:
        async with session_scope() as s:
            # Ensure the user row exists so the FK is satisfied.
            row = await s.get(UserProfile, user_id)
            if row is None:
                s.add(UserProfile(user_id=user_id))
                await s.flush()
            s.add(SessionTurn(
                user_id=user_id,
                session_id=session_id,
                query=query[:2000],
                intent=intent.value,
                envelope=envelope,
            ))
    except SQLAlchemyError:
        logger.exception("memory.record_turn failed user=%s", user_id)


async def recent_turns(user_id: str, *, limit: int = _RECENT_TURN_LIMIT
                          ) -> list[MemorySessionTurn]:
    if not is_ready():
        return []
    try:
        async with session_scope() as s:
            stmt = (select(SessionTurn)
                     .where(SessionTurn.user_id == user_id)
                     .order_by(SessionTurn.created_at.desc())
                     .limit(limit))
            rows = (await s.execute(stmt)).scalars().all()
            return [_turn_from_row(r) for r in rows]
    except SQLAlchemyError:
        logger.exception("memory.recent_turns failed user=%s", user_id)
        return []


# --- activity -------------------------------------------------------------

async def record_activity(*, user_id: str, event_type: str,
                            payload: dict | None = None) -> None:
    if not is_ready():
        return
    try:
        async with session_scope() as s:
            row = await s.get(UserProfile, user_id)
            if row is None:
                s.add(UserProfile(user_id=user_id))
                await s.flush()
            s.add(ActivityEvent(
                user_id=user_id,
                event_type=event_type[:48],
                payload=payload or {},
            ))
    except SQLAlchemyError:
        logger.exception("memory.record_activity failed user=%s", user_id)


async def recent_activity(user_id: str, *, limit: int = _RECENT_ACTIVITY_LIMIT
                             ) -> list[MemoryActivity]:
    if not is_ready():
        return []
    try:
        async with session_scope() as s:
            stmt = (select(ActivityEvent)
                     .where(ActivityEvent.user_id == user_id)
                     .order_by(ActivityEvent.created_at.desc())
                     .limit(limit))
            rows = (await s.execute(stmt)).scalars().all()
            return [_activity_from_row(r) for r in rows]
    except SQLAlchemyError:
        logger.exception("memory.recent_activity failed user=%s", user_id)
        return []


# --- composite readout ----------------------------------------------------

async def readout(user_id: str, *, country: str = "IN") -> MemoryReadout:
    """Top-level fan-out used by the orchestrator's memory.readout layer-call."""
    profile = await get_or_create_profile(user_id, country=country)
    turns = await recent_turns(user_id)
    activity = await recent_activity(user_id)
    return MemoryReadout(profile=profile, recent_turns=turns,
                          recent_activity=activity)


# --- model -> schema -----------------------------------------------------

def _profile_from_row(row: UserProfile) -> MemoryProfile:
    return MemoryProfile(
        user_id=row.user_id,
        country=row.country,
        age=row.age,
        risk_tolerance=(RiskLevel(row.risk_tolerance)
                         if row.risk_tolerance else None),
        goal=row.goal,
        income_bracket=row.income_bracket,
        comprehension_level=row.comprehension_level,
        instrument_type=(InstrumentType(row.instrument_type)
                          if row.instrument_type else None),
        amount=float(row.amount) if row.amount is not None else None,
        horizon_years=row.horizon_years,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _turn_from_row(row: SessionTurn) -> MemorySessionTurn:
    try:
        intent = Intent(row.intent)
    except ValueError:
        intent = Intent.UNKNOWN
    return MemorySessionTurn(
        session_id=row.session_id,
        query=row.query,
        intent=intent,
        created_at=row.created_at,
    )


def _activity_from_row(row: ActivityEvent) -> MemoryActivity:
    return MemoryActivity(
        event_type=row.event_type,
        payload=row.payload or {},
        created_at=row.created_at,
    )
