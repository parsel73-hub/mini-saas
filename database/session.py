"""Engine, session factory and FastAPI session dependency."""
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from database.base import Base

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _migrate_sqlite() -> None:
    """Add columns introduced after the initial schema for SQLite databases.

    ``Base.metadata.create_all`` never alters existing tables, so databases
    created on earlier stages miss newly added columns. This idempotent helper
    adds them in place without dropping data.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "surveys" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("surveys")}
    if "is_active" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE surveys ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
            )


def init_db() -> None:
    """Create all tables. Models must be imported before calling."""
    # Import models so they are registered on Base.metadata.
    from auth import models as auth_models  # noqa: F401  # isort: skip
    from database import models as core_models  # noqa: F401  # isort: skip

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def get_db() -> Generator[Session, None, None]:
    """Yield a per-request SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
