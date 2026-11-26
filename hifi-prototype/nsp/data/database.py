"""Database set-up: one SQLite file, one session per web request."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from ..domain import Base


class Database:
    def __init__(self, url: str = "sqlite:///nsp_demo.db") -> None:
        options: dict = {}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # An in-memory database must share a single connection.
            options = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        self.engine = create_engine(url, **options)
        self.session: scoped_session[Session] = scoped_session(
            sessionmaker(bind=self.engine, expire_on_commit=False)
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        self.session.remove()
        Base.metadata.drop_all(self.engine)

    def reset(self) -> None:
        self.drop_all()
        self.create_all()
