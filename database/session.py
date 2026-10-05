"""Engine, session factory and FastAPI session dependency."""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from database.base import Base

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables. Models must be imported before calling."""
    # Import models so they are registered on Base.metadata.
    from auth import models as auth_models  # noqa: F401  # isort: skip
    from database import models as core_models  # noqa: F401  # isort: skip

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a per-request SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
