"""Deterministic infrastructure layers.

Each layer is pure code + I/O. Layers must not import from `app.agents.*` or
`app.orchestrator.*` (one-way dependency, enforced by .importlinter).
"""
