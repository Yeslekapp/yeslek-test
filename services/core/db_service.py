# ---------------------------
# PostgreSQL DB Service
# ---------------------------

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool


logger = logging.getLogger(__name__)

_pool: SimpleConnectionPool | None = None


# ---------------------------
# Database URL
# ---------------------------

def _database_url() -> str:
    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DSN")
        or ""
    ).strip()

    if not url:
        raise RuntimeError("missing_database_url")

    return url


# ---------------------------
# Pool
# ---------------------------

def _get_pool() -> SimpleConnectionPool:
    global _pool

    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=int(os.getenv("DB_POOL_MIN", "1")),
            maxconn=int(os.getenv("DB_POOL_MAX", "10")),
            dsn=_database_url(),
        )

    return _pool


# ---------------------------
# Cursor
# ---------------------------

@contextmanager
def db_cursor(
    *,
    commit: bool = False,
) -> Generator[RealDictCursor, None, None]:

    pool = _get_pool()
    conn = pool.getconn()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur

        if commit:
            conn.commit()

    except Exception:
        conn.rollback()
        logger.exception("Database transaction error")
        raise

    finally:
        pool.putconn(conn)