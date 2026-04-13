from collections.abc import Generator
import logging
import time

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db.base import Base

logger = logging.getLogger(__name__)


def create_db_engine() -> Engine:
    settings = get_settings()
    database_url = settings.database_url

    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

    return create_engine(database_url, pool_pre_ping=True)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialize_database() -> None:
    import app.models  # noqa: F401

    settings = get_settings()
    last_error: Exception | None = None

    for attempt in range(1, settings.database_init_max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized on attempt %s", attempt)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Database initialization attempt %s/%s failed: %s",
                attempt,
                settings.database_init_max_attempts,
                exc,
            )
            if attempt == settings.database_init_max_attempts:
                break
            time.sleep(settings.database_init_retry_delay_seconds)

    assert last_error is not None
    raise last_error


def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
