"""Uma, varias e todas as empresas; consolidado = soma; credito nao compensa entre empresas."""
from __future__ import annotations

import pytest

from tests.fixtures.gerador import gerar_conjunto
from zfm import beneficio_atual as ba
from zfm import db, params, simulacao, visoes
from zfm.parsers import carregar_arquivo


def test_consolidado_igual_soma(con_param):
    det = ba.calcular(con_param)
    por = det.groupby("raiz")["beneficio"].sum()
    assert por.sum() == pytest.approx(det["beneficio"].sum())
    anual, _ = simulacao.simular(con_param)
    a = anual[(anual.cenario == "base") & (anual.ano == 2033)]
    assert a["beneficio_pos"].sum() == pytest.approx(a.groupby("raiz")["beneficio_pos"].sum().sum())
    assert set(a["raiz"]) == {"11111111", "22222222", "33333333"}


def test_operacao_entre_empresas_identificada(con_param):
    r = con_param.execute("""SELECT DISTINCT raiz FROM v_docs WHERE eh_grupo""").fetchall()
    assert {x[0] for x in r} == {"11111111", "22222222"}


def test_credito_de_uma_empresa_nao_abate_outra(con_param, tmp_path, monkeypatch):
    anual, _ = simulacao.simular(con_param)
    alfa_todas = anual[(anual.raiz == "11111111") & (anual.cenario == "base")].set_index("ano")
    # banco so com a Alfa (mesmos parametros)
    pasta = tmp_path / "so_alfa"
    gerar_conjunto(pasta)
    con2 = db.conectar(tmp_path / "so_alfa.duckdb")
    for p in sorted(pasta.glob("*11111111*.txt")):
        carregar_arquivo(con2, p)
    visoes.preparar(con2)
    a2, _ = simulacao.simular(con2)
    alfa_so = a2[(a2.raiz == "11111111") & (a2.cenario == "base")].set_index("ano")
    for col in ("cbs_pagar", "ibs_pagar", "beneficio_pos"):
        assert alfa_so[col].round(2).equals(alfa_todas[col].round(2)), col
    # e a Beta tem saldo credor estrutural que nao foi usado pela Alfa
    beta = anual[(anual.raiz == "22222222") & (anual.cenario == "base") & (anual.ano == 2033)]
    assert float(beta["meses_saldo_credor"].iloc[0]) == 12
