"""Database session management via SQLAlchemy Core.

Replaces both get_platform_db() and get_hub_db() with a single get_db()
context manager that yields a SA Connection with auto-commit/rollback.
"""

from contextlib import contextmanager

from app.db.engine import engine


@contextmanager
def get_db():
    """Get a database connection from the SA engine.

    Replaces both get_platform_db() and get_hub_db(). All hub data is
    now read from hub_* mirror tables within the same database.

    Usage::

        with get_db() as conn:
            result = conn.execute(hub_todos.select().where(...))
    """
    with engine.connect() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
