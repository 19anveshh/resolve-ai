"""FastAPI dependencies shared by API routes."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_session


def get_db() -> Generator[Session, None, None]:
    """Provide one request-scoped database session."""

    yield from get_session()
