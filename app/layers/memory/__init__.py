"""Memory layer: persistent user profile, session history, activity log.

Public surface (the only things the orchestrator calls):
  - init_memory(), close_memory()  : DB lifecycle from FastAPI lifespan
  - readout(user_id, session_id)   : load profile + recent turns + activity
  - get_or_create_profile(user_id) : ensure a row exists
  - update_profile(user_id, ...)   : merge new profile facts
  - record_turn(...)               : persist a (query, intent, envelope) tuple
  - record_activity(...)           : persist a typed user-action event

The repo functions catch and log exceptions, so a DB outage degrades to
empty readouts rather than 500s. The orchestrator treats memory as a soft
dependency.
"""
from app.layers.memory.db import close_memory, init_memory
from app.layers.memory.repo import (get_or_create_profile, readout,
                                       record_activity, record_turn,
                                       update_profile)

__all__ = [
    "close_memory",
    "get_or_create_profile",
    "init_memory",
    "readout",
    "record_activity",
    "record_turn",
    "update_profile",
]
