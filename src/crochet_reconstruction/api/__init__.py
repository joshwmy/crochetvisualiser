"""Visualizer compile API: a focused FastAPI app, separate from the portal.

Deliberately its own module tree (not folded into ``portal/``) — this is a
stateless compile endpoint for the scientific viewer, with no database, no
authentication, and no contributor/consent business logic. See
``docs/compile-api.md``.
"""

from __future__ import annotations
