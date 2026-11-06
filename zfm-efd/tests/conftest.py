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


@pytest.fixture
def con_param(con_carregado):
    """Base carregada + parametros preenchidos a partir das EFDs + TIPI dos produtos."""
    from zfm import params, visoes
    visoes.preparar(con_carregado)
    params.preencher_a_partir_das_efds(con_carregado)
    pr = params.carregar("param_produtos")
    pr.loc[pr.cod_item == "PROD01", "aliq_tipi_2023"] = 15.0
    pr.loc[pr.cod_item == "PROD02", "aliq_tipi_2023"] = 5.0
    params.salvar("param_produtos", pr)
    visoes.preparar(con_carregado)
    return con_carregado
