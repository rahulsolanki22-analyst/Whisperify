import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Database configuration (using SQLite with aiosqlite for async support)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./whisperify.db")

# Create asynchronous engine
# connect_args={"check_same_thread": False} is required only for SQLite to allow multi-threaded access in async contexts
async_engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,  # Set to True if database query logging is needed for debugging
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Modern SQLAlchemy 2.0 Base class
class Base(DeclarativeBase):
    pass

# Dependency injection generator for route handlers
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to yield an async database session.
    Automatically handles cleanup/close after request lifecycle.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
