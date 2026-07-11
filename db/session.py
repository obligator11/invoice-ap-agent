from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import settings
from db.models import Base

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables if they don't exist yet.

    For a real deployment you'd use Alembic migrations instead of this —
    see db/schema.sql for the equivalent versioned-migration starting point.
    This function is here so `streamlit run app.py` works on a fresh
    Postgres instance with zero extra steps for local dev/demo.
    """
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Usage:
        with get_session() as db:
            db.add(obj)
            db.commit()
    """
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
