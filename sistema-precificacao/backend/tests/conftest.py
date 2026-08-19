"""Fixtures de teste: banco SQLite em memoria, criado a partir do metadata."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


@pytest.fixture()
def engine():
    motor = create_engine("sqlite+pysqlite:///:memory:", future=True)

    # SQLite ignora chaves estrangeiras por padrao; sem isso o teste de
    # integridade referencial passaria por engano.
    @event.listens_for(motor, "connect")
    def _ativar_fk(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(motor)
    yield motor
    motor.dispose()


@pytest.fixture()
def sessao(engine) -> Iterator[Session]:
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with fabrica() as s:
        yield s
