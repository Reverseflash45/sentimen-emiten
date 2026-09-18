"""Koneksi basis data dan pembuatan sesi."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """Dependency FastAPI: satu sesi per permintaan."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
