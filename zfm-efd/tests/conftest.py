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


@pytest.fixture(scope="session")
def _banco_modelo(tmp_path_factory):
    """Carrega as EFDs sinteticas uma vez por sessao; cada teste recebe uma copia do banco."""
    import os
    pasta = tmp_path_factory.mktemp("modelo")
    antigo = os.environ.get("ZFM_DATA_DIR")
    os.environ["ZFM_DATA_DIR"] = str(pasta / "data")
    try:
        gerar_conjunto(pasta / "efd")
        c = db.conectar(pasta / "modelo.duckdb")
        for p in sorted((pasta / "efd").glob("*.txt")):
            r = carregar_arquivo(c, p)
            assert r.situacao == "carregado", r.mensagem
        c.close()
    finally:
        if antigo is None:
            os.environ.pop("ZFM_DATA_DIR", None)
        else:
            os.environ["ZFM_DATA_DIR"] = antigo
    return pasta / "modelo.duckdb"


@pytest.fixture
def con_carregado(tmp_path, _banco_modelo):
    import shutil
    destino = tmp_path / "carregado.duckdb"
    shutil.copyfile(_banco_modelo, destino)
    c = db.conectar(destino)
    yield c
    c.close()


@pytest.fixture
def con_param(con_carregado):
    """Base carregada + parametros preenchidos a partir das EFDs + TIPI dos produtos."""
    from zfm import params, visoes
    visoes.preparar(con_carregado)
    params.preencher_a_partir_das_efds(con_carregado)
    pr = params.carregar("param_produtos")
    pr.loc[pr.cod_item == "PROD01", "aliq_ipi"] = 15.0
    pr.loc[pr.cod_item == "PROD02", "aliq_ipi"] = 5.0
    params.salvar("param_produtos", pr)
    visoes.preparar(con_carregado)
    return con_carregado
