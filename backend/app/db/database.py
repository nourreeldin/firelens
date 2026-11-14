"""Reusable asyncpg connection pool and raw-SQL execution helpers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from app.core.config import Settings
from app.core.exceptions import DatabaseExecutionError, DatabaseUnavailableError

logger = logging.getLogger(__name__)


def _is_unavailable_error(exc: BaseException) -> bool:
    """Return whether an asyncpg failure means the database is unavailable."""
    return isinstance(
        exc,
        (
            OSError,
            TimeoutError,
            asyncio.TimeoutError,
            asyncpg.InterfaceError,
            asyncpg.exceptions.PostgresConnectionError,
        ),
    )


class Database:
    """Small wrapper around an asyncpg pool.

    All query values must be passed separately and referenced with PostgreSQL
    placeholders (``$1``, ``$2``, ...). Repositories only interpolate trusted,
    code-defined SQL fragments.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, settings: Settings) -> Database:
        """Create and warm a connection pool using the existing DATABASE_URL."""
        pool: asyncpg.Pool | None = None
        try:
            pool = await asyncpg.create_pool(
                dsn=settings.database_dsn,
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
                timeout=settings.database_connect_timeout,
                command_timeout=settings.database_command_timeout,
            )
            if pool is None:  # pragma: no cover - defensive for older asyncpg
                raise RuntimeError("asyncpg did not create a connection pool")
            database = cls(pool)
            await database.check()
            return database
        except DatabaseUnavailableError:
            if pool is not None:
                await pool.close()
            raise
        except Exception as exc:
            if pool is not None:
                await pool.close()
            logger.error(
                "Database pool initialization failed (%s).", type(exc).__name__
            )
            raise DatabaseUnavailableError(
                "Database connection could not be established."
            ) from exc

    async def close(self) -> None:
        """Close all pooled connections."""
        await self._pool.close()

    def _raise_translated(self, exc: BaseException) -> None:
        if isinstance(exc, (DatabaseUnavailableError, DatabaseExecutionError)):
            raise exc
        if _is_unavailable_error(exc):
            logger.error("Database connection failure (%s).", type(exc).__name__)
            raise DatabaseUnavailableError("Database is unavailable.") from exc
        if isinstance(exc, asyncpg.PostgresError):
            logger.error("Database query failure (%s).", type(exc).__name__)
            raise DatabaseExecutionError("A database query failed.") from exc
        raise exc

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and return all rows."""
        try:
            return list(await self._pool.fetch(query, *args))
        except Exception as exc:
            self._raise_translated(exc)
            raise  # unreachable, keeps type checkers happy

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a query and return the first row, if any."""
        try:
            return await self._pool.fetchrow(query, *args)
        except Exception as exc:
            self._raise_translated(exc)
            raise  # unreachable

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return its first scalar value."""
        try:
            return await self._pool.fetchval(query, *args)
        except Exception as exc:
            self._raise_translated(exc)
            raise  # unreachable

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a statement and return its status string."""
        try:
            return await self._pool.execute(query, *args)
        except Exception as exc:
            self._raise_translated(exc)
            raise  # unreachable

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire one connection, translating pool and query failures."""
        try:
            async with self._pool.acquire() as connection:
                yield connection
        except Exception as exc:
            self._raise_translated(exc)
            raise  # unreachable

    async def check(self) -> None:
        """Verify the database is reachable with a trivial parameterless query."""
        try:
            value = await self._pool.fetchval("SELECT 1")
        except Exception as exc:
            self._raise_translated(exc)
            raise  # unreachable
        if value != 1:
            raise DatabaseUnavailableError("Database readiness check failed.")
