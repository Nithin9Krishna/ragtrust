from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class PublicWorkspace:
    """An ephemeral database and upload directory owned by one browser session."""

    def __init__(self):
        self._directory = TemporaryDirectory(prefix="ragtrust-visitor-")
        self.data_dir = Path(self._directory.name)
        self.engine = create_engine(
            f"sqlite:///{self.data_dir / 'workspace.db'}",
            connect_args={"check_same_thread": False},
        )
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.created_at = monotonic()
        from . import models  # noqa: F401
        Base.metadata.create_all(self.engine)

    @property
    def expired(self) -> bool:
        return monotonic() - self.created_at > 2 * 60 * 60

    def close(self) -> None:
        self.engine.dispose()
        self._directory.cleanup()

    def __del__(self):
        if hasattr(self, "engine"):
            self.close()


_workspace: ContextVar[PublicWorkspace | None] = ContextVar("ragtrust_workspace", default=None)


def activate_workspace(workspace: PublicWorkspace | None):
    return _workspace.set(workspace)


def reset_workspace(token) -> None:
    _workspace.reset(token)


def current_workspace() -> PublicWorkspace | None:
    workspace = _workspace.get()
    if settings.public_demo and workspace is None:
        raise RuntimeError("Public demo requires an isolated visitor workspace")
    return workspace


def workspace_data_dir() -> Path:
    workspace = current_workspace()
    return workspace.data_dir if workspace else settings.data_dir


def init_db() -> None:
    from . import models  # noqa: F401
    workspace = current_workspace()
    Base.metadata.create_all(workspace.engine if workspace else engine)


def session_scope():
    workspace = current_workspace()
    return workspace.sessions() if workspace else SessionLocal()
