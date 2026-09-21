"""Koneksi basis data dan pembuatan sesi."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def _rapikan_url(url: str) -> str:
    """Supabase memberi URL berawalan `postgresql://` (atau `postgres://`), yang
    oleh SQLAlchemy diartikan sebagai driver psycopg2. Proyek ini memakai
    psycopg 3, jadi drivernya disebut eksplisit."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


URL = _rapikan_url(settings.database_url)

if URL.startswith("sqlite"):
    engine = create_engine(URL, connect_args={"check_same_thread": False}, future=True)
else:
    # Di Vercel setiap permintaan bisa dilayani instans fungsi yang berbeda dan
    # berumur pendek, jadi kolam koneksi milik aplikasi tidak berguna — kolamnya
    # sudah disediakan pooler Supabase (port 6543). Pooler itu memakai mode
    # transaksi, yang tidak mendukung prepared statement.
    pakai_pooler = make_url(URL).port == 6543
    engine = create_engine(
        URL,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None} if pakai_pooler else {},
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """Dependency FastAPI: satu sesi per permintaan."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
