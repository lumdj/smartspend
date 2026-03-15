"""
SmartSpend Database
Manages the SQLAlchemy engine, session factory, and dependency injection.

Security notes:
- Connection pool is sized conservatively to prevent connection exhaustion attacks
- pool_pre_ping=True drops stale connections rather than erroring mid-request
- Sessions are always closed in the finally block via the generator pattern
- The engine is created once at module load, not per-request
"""

from sqlmodel import SQLModel, create_engine, Session
from config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Convert pydantic's PostgresDsn to a plain string for SQLAlchemy
_db_url = str(settings.database_url)

# In test environments, use SQLite for speed and isolation
if settings.environment == "test":
    _db_url = "sqlite:///./test.db"
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(
    _db_url,
    connect_args=connect_args,
    # Pool settings — conservative for free-tier Render (max 25 connections)
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,       # Verify connection health before use
    pool_recycle=1800,        # Recycle connections after 30 min
    # NEVER echo SQL in production — it logs query params which may contain PII
    echo=settings.environment == "development",
)


def get_session():
    """
    FastAPI dependency — yields a database session and ensures it is always
    closed, even if the request handler raises an exception.

    Usage in routers:
        from fastapi import Depends
        from database import get_session
        from sqlmodel import Session

        @router.get("/example")
        def example(db: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def create_db_and_tables():
    """
    Creates all tables defined in SQLModel metadata.
    Called once on startup in development.
    In production, Alembic migrations handle this instead.
    """
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables verified/created")
