"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool

from config.db_config import get_settings

settings = get_settings()

# Construct the database URL from settings
DATABASE_URL = f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# Create an asynchronous database engine
engine = create_async_engine(
    DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=False,  # Set to True to log SQL statements
)

# Create a factory for asynchronous database sessions
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create a base class for declarative models
Base = declarative_base()


# Dependency function to get a database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async database session.

    This is a generator that yields a session and ensures it's properly
    closed after the request is finished. It also handles committing
    transactions on success or rolling back on failure.

    Usage:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
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
