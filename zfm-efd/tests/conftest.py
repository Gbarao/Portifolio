"""Fixtures dos testes: EFDs sinteticas geradas em pasta temporaria."""
from __future__ import annotations

import pytest

from tests.fixtures.gerador import gerar_conjunto
from zfm import db
from zfm.parsers import carregar_arquivo


@pytest.fixture(autouse=True)
def _pasta_dados_temporaria(tmp_path, monkeypatch):
    monkeypatch.setenv("ZFM_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def con(tmp_path):
    c = db.conectar(tmp_path / "teste.duckdb")
    yield c
    c.close()


@pytest.fixture
def pasta_efd(tmp_path):
    pasta = tmp_path / "efd"
    gerar_conjunto(pasta)
    return pasta


@pytest.fixture
def con_carregado(con, pasta_efd):
    for p in sorted(pasta_efd.glob("*.txt")):
        r = carregar_arquivo(con, p)
        assert r.situacao == "carregado", r.mensagem
    return con
