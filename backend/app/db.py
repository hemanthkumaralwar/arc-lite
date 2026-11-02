from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings


def _with_psycopg_driver(url: str) -> str:
    """Neon and most dashboards give 'postgresql://'. SQLAlchemy needs the psycopg driver named explicitly."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def make_engine(url: str):
    return create_engine(_with_psycopg_driver(url), pool_pre_ping=True)


engine = make_engine(settings.database_url) if settings.database_url else None
SessionLocal = sessionmaker(bind=engine, autoflush=False) if engine is not None else None
