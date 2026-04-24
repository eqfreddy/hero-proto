from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# SQLite ignores ON DELETE CASCADE by default — you have to ask for it on every
# connection. Postgres enforces FKs natively; the listener fires on any connection
# but the PRAGMA is a no-op outside SQLite, so guard it.
@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _conn_record) -> None:
    # Detect SQLite via driver module rather than url string — works for both the
    # main engine and test-spawned engines.
    if dbapi_conn.__class__.__module__.startswith("sqlite3"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
