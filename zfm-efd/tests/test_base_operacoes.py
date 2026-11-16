"""Base de operacoes: uma fonte por visao, devolucoes abatidas, transferencias a parte."""
from __future__ import annotations

import pytest


def test_sem_dupla_contagem_de_saidas(con_param):
    base, contrib = con_param.execute("""
        SELECT (SELECT sum(valor) FROM v_base_operacoes WHERE sentido = 'saida'
                  AND natureza NOT IN ('devolucao_venda')),
               (SELECT sum(CAST(receita AS DOUBLE)) FROM v_saidas_item s LEFT JOIN param_cfops pc ON pc.cfop = s.cfop
                  WHERE s.estab_no_am AND coalesce(pc.devolucao_de, '') = '')""").fetchall()[0]
    assert base == pytest.approx(contrib)


def test_devolucao_de_venda_negativa(con_param):
    d = con_param.execute("""SELECT natureza, categoria_origem, tipo_operacao, valor FROM v_base_operacoes
                             WHERE raiz = '11111111' AND cfop = '2201'""").fetchall()
    assert d == [("devolucao_venda", "venda_producao", "interestadual", -40000.0)]


def test_devolucao_de_compra_negativa(con_param):
    d = con_param.execute("""SELECT sentido, natureza, categoria_origem, origem, valor FROM v_base_operacoes
                             WHERE raiz = '11111111' AND cfop = '6201'""").fetchall()
    assert d == [("entrada", "devolucao_compra", "compra_industrializacao", "nacional_fora_zfm", -10000.0)]
    # a mesma devolucao nao aparece de novo como saida
    n = con_param.execute("""SELECT count(*) FROM v_base_operacoes
                             WHERE raiz = '11111111' AND cfop = '6201' AND sentido = 'saida'""").fetchall()[0][0]
    assert n == 0


def test_transferencias_identificadas(con_param):
    d = dict(con_param.execute("""SELECT sentido, sum(valor) FROM v_base_operacoes
                                  WHERE natureza = 'transferencia' GROUP BY 1""").fetchall())
    assert d == {"saida": 5000.0, "entrada": 5000.0}


def test_exportacao_fica_na_base_sem_debito(con_param):
    # nao ha exportacao nas fixtures de saida; o motor exclui 'exportacao' do debito (ver simulacao)
    from zfm import simulacao
    i = simulacao.insumos_mensais(con_param)
    assert "exportacao" in i.columns
