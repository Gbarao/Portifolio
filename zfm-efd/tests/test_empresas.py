"""Uma, varias e todas as empresas; consolidado = soma; credito nao compensa entre empresas."""
from __future__ import annotations

import pytest

from tests.fixtures.gerador import gerar_conjunto
from zfm import beneficio_atual as ba
from zfm import db, simulacao, visoes
from zfm.filtros import Filtro
from zfm.parsers import carregar_arquivo


def test_consolidado_igual_soma(con_param):
    det = ba.calcular(con_param)
    assert det.groupby("raiz")["beneficio"].sum().sum() == pytest.approx(det["beneficio"].sum())
    anual, _ = simulacao.simular(con_param)
    a = anual[(anual.cenario == "base") & (anual.ano == 2033)]
    assert set(a["raiz"]) == {"11111111", "22222222", "33333333"}
    # simular so uma empresa da o mesmo resultado que a linha dela no consolidado
    so_beta, _ = simulacao.simular(con_param, Filtro(raizes=("22222222",)))
    b1 = so_beta[(so_beta.cenario == "base") & (so_beta.ano == 2033)].iloc[0]
    b2 = a[a.raiz == "22222222"].iloc[0]
    for col in ("as_is_total", "to_be_total", "diferenca_total"):
        assert b1[col] == pytest.approx(b2[col])


def test_operacao_entre_empresas_identificada(con_param):
    r = con_param.execute("""SELECT DISTINCT raiz FROM v_docs WHERE eh_grupo""").fetchall()
    assert {x[0] for x in r} == {"11111111", "22222222"}


def test_credito_de_uma_empresa_nao_abate_outra(con_param, tmp_path):
    anual, _ = simulacao.simular(con_param)
    alfa_todas = anual[(anual.raiz == "11111111") & (anual.cenario == "base")].set_index("ano")
    pasta = tmp_path / "so_alfa"
    gerar_conjunto(pasta)
    con2 = db.conectar(tmp_path / "so_alfa.duckdb")
    for p in sorted(pasta.glob("*11111111*.txt")):
        carregar_arquivo(con2, p)
    visoes.preparar(con2)
    a2, _ = simulacao.simular(con2)
    alfa_so = a2[(a2.raiz == "11111111") & (a2.cenario == "base")].set_index("ano")
    for col in ("to_be_cbs", "to_be_ibs", "diferenca_total"):
        assert alfa_so[col].round(2).equals(alfa_todas[col].round(2)), col
    beta = anual[(anual.raiz == "22222222") & (anual.cenario == "base") & (anual.ano == 2033)]
    assert float(beta["meses_saldo_credor"].iloc[0]) == 12


def test_filtro_por_estabelecimento(con_param):
    from zfm import as_is
    todos = as_is.carga_mensal(con_param)
    so1 = as_is.carga_mensal(con_param, Filtro(estabs=("11111111000191",)))
    icms_todos = todos[(todos.raiz == "11111111") & (todos.tributo == "ICMS")]["carga"].sum()
    icms_so1 = so1[(so1.raiz == "11111111") & (so1.tributo == "ICMS")]["carga"].sum()
    assert icms_so1 < icms_todos and icms_so1 > 0
    assert set(so1.loc[so1.tributo == "ICMS", "cnpj_estab"]) == {"11111111000191"}
