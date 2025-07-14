"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from db.db_config import get_settings
from utils.logger import logger

# --- Database Setup ---

# Load database settings
settings = get_settings()

# Construct the database URL from the settings
DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# Global variables for the database engine and session factory
engine = None
SessionLocal = None


def init_db():
    """
    Initializes the database engine and session factory.

    This function creates a SQLAlchemy engine with a connection pool and sets up
    a sessionmaker to create new database sessions. It also tests the connection.
    """
    global engine, SessionLocal
    if engine is not None:
        logger.info("Database engine is already initialized.")
        return

    try:
        logger.info("Initializing database engine...")
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,  # Test connections for liveness before using them.
            pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections after a set time.
            pool_size=settings.DB_POOL_SIZE,  # Set the connection pool size.
            max_overflow=settings.DB_MAX_OVERFLOW,  # Set the connection pool overflow.
            echo=False,  # Do not log all SQL statements.
            connect_args={
                "connect_timeout": 10,
                "charset": "utf8mb4",
                "use_unicode": True,
                "autocommit": True,  # Enable autocommit for the underlying DBAPI connection.
                "program_name": "st_engine",
            },
        )
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        # Test the database connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection successful.")

    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        # Reset globals on failure
        engine = None
        SessionLocal = None
        raise


@contextmanager
def get_db_session() -> Iterator[Session]:
    """
    Provides a transactional scope around a series of operations.

    This context manager ensures that the database session is properly
    initialized and closed, and handles connection errors by attempting to
    re-establish the connection.

    Yields:
        Session: A new SQLAlchemy session object.
    """
    global engine, SessionLocal
    if engine is None or SessionLocal is None:
        logger.warning("Database not initialized. Attempting to initialize now.")
        init_db()

    if SessionLocal is None:
        raise RuntimeError("Failed to initialize database session factory")

    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"An error occurred during the database session: {e}")
        # In case of a connection error, it might be beneficial to rollback.
        session.rollback()
        raise
    finally:
        session.close()
