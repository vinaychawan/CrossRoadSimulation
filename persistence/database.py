"""Database session factory and helpers."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from persistence.models import Base

_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./crossroads.db")

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in _DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables (used when not running Alembic migrations)."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """FastAPI dependency: yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
