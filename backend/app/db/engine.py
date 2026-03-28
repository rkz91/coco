"""SQLAlchemy engine singleton for platform.db (SQLite) or PostgreSQL.

All SA Core queries go through this engine.  When DATABASE_URL is not set,
the engine defaults to SQLite with WAL journal mode, busy_timeout, and
foreign keys.  When DATABASE_URL points to PostgreSQL, connection pooling
is configured instead.
"""

import os

from sqlalchemy import create_engine, event
from app.config import DATABASE_URL, PLATFORM_DB_PATH

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"timeout": 10},
        pool_pre_ping=True,
        # SQLite uses NullPool by default in SA, which is fine for us
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, connection_record):
        """Mirror the PRAGMA settings from connections._connect."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # PostgreSQL (or any non-SQLite database)
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
