"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool

from config.db_config import get_settings

# --- Database Setup ---

settings = get_settings()

# Construct the asynchronous database URL.
DATABASE_URL = (
    f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# Create an asynchronous engine.
engine = create_async_engine(
    DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,  # Use an asyncio-compatible connection pool.
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=False,  # Do not log all SQL statements.
)

# Create an asynchronous session factory.
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit.
    autocommit=False,
    autoflush=False,
)

# Base class for declarative models.
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get an asynchronous database session.

    This generator function yields a new `AsyncSession` for each request
    and handles committing, rolling back, and closing the session.

    Usage:
    ```python
    from fastapi import Depends

    @app.get("/items")
    async def read_items(db: AsyncSession = Depends(get_db)):
        # ... use the session `db` ...
    ```

    Yields:
        AsyncSession: The database session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
