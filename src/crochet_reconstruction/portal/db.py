"""SQLAlchemy engine/session setup.

One process-wide engine, created lazily from `Settings.database_url`. Tests
override this via `create_engine_for_settings` directly rather than relying
on global state, so the test suite never touches a developer's real
`portal_data/portal.db`.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from crochet_reconstruction.portal.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def create_engine_for_settings(settings: Settings) -> Engine:
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, connect_args=connect_args)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_database(settings: Settings) -> None:
    global _engine, _session_factory
    _engine = create_engine_for_settings(settings)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_engine() -> Engine:
    if _engine is None:
        configure_database(get_settings())
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        configure_database(get_settings())
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, closed afterward."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def create_all_tables() -> None:
    """Used by tests and the initial pilot setup. Real deployments use Alembic."""
    Base.metadata.create_all(bind=get_engine())
