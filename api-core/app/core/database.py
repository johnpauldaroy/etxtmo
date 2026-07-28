from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)
Base = declarative_base()


class UTCDateTime(TypeDecorator):
    """
    DateTime(timezone=True) that is actually timezone-aware everywhere.

    SQLite has no native tz-aware datetime type, so SQLAlchemy silently
    stores and returns naive datetimes for it (Postgres/MySQL do not have
    this problem). Naive UTC values then serialize without a "Z"/offset,
    which browsers parse as local time -- shifting every timestamp shown
    in the UI by the viewer's UTC offset. This type always attaches UTC
    tzinfo on the way out, regardless of dialect.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

