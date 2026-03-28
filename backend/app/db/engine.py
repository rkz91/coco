"""SQLAlchemy Core engine factory.

Provides a single engine instance configured from DATABASE_URL.
Defaults to SQLite (platform.db) but supports PostgreSQL for cloud deployment.
"""

from sqlalchemy import create_engine, event
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Set WAL mode, busy timeout, and foreign keys for SQLite connections."""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
