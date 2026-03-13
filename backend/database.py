"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

connect_args: dict[str, bool] = {}
if settings.database_dialect == "sqlite":
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,
    connect_args=connect_args,
)
if settings.database_dialect != "sqlite":
    # fast_executemany 为 SQL Server 推荐优化，SQLite 不支持该参数
    engine = create_engine(
        settings.get_database_url(),
        pool_pre_ping=True,
        fast_executemany=True,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """Yield a SQLAlchemy session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
