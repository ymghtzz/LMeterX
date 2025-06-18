"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.mysql import async_session_factory


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    An asynchronous context manager for database sessions.

    This function provides a convenient way to get a database session that is
    automatically committed, rolled back on error, and closed.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
