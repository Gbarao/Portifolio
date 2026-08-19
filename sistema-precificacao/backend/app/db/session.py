"""Engine e fabrica de sessoes."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    echo=False,
    future=True,
    # SQLite (desenvolvimento e testes) precisa disso para aceitar a sessao
    # em threads distintas; em PostgreSQL o argumento e ignorado.
    connect_args={"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependencia de sessao por requisicao."""

    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()
