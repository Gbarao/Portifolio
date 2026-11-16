"""Carga As Is lida da apuracao (sem recalculo) - valores de janeiro conferidos a mao.

Alfa 0001, jan: debitos 70.000 (C190), creditos 9.400 -> apurado 60.600; credito estimulo
  (deducao) 38.500 -> ICMS a recolher 22.100; E116 = 22.100 (COD_OR 000) + 385 (FTI) = 22.485.
  Premissa padrao 'e110_mais_excesso_e116': carga = 22.100 + (22.485 − 22.100) = 22.485.
Alfa 0002, jan: 18.000 − 2.800 = 15.200.
Beta, jan: creditos > debitos (saldo credor) -> ICMS 0.
PIS/COFINS: M200/M600 VL_TOT_CONT_REC. Gama tem matriz em SP: rateio pela receita do AM
  (jan: 200.000 / 210.000) sobre PIS de 1.300 + 165 = 1.465.
"""
from __future__ import annotations

import pytest

from zfm import as_is, params


def _jan(m, raiz, trib):
    return m[(m.raiz == raiz) & (m.mes == 1) & (m.tributo == trib)]["carga"].sum()


def test_icms_lido_da_apuracao(con_param):
    m = as_is.carga_mensal(con_param)
    assert _jan(m, "11111111", "ICMS") == pytest.approx(22485.0 + 15200.0)
    assert _jan(m, "22222222", "ICMS") == 0
    assert _jan(m, "11111111", "IPI") == 0
    a1 = m[(m.cnpj_estab == "11111111000191") & (m.mes == 1) & (m.tributo == "ICMS")].iloc[0]
    assert a1["credito_estimulo"] == 38500.0 and a1["fundos_fora_apuracao"] == pytest.approx(385.0)
    # decomposicao fecha: saidas + entradas + deducoes + fundos + saldo = carga
    soma = a1[["saidas_debitos", "entradas_creditos", "deducoes_beneficios", "fundos_fora_apuracao",
               "efeito_saldo"]].sum()
    assert soma == pytest.approx(a1["carga"])


def test_premissa_da_carga_de_icms(con_param):
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "carga_icms_as_is", "valor"] = "somente_e110"
    params.salvar("param_premissas", pr)
    m = as_is.carga_mensal(con_param)
    assert _jan(m, "11111111", "ICMS") == pytest.approx(22100.0 + 15200.0)


def test_pis_cofins_com_rateio_do_am(con_param):
    m = as_is.carga_mensal(con_param)
    assert _jan(m, "22222222", "PIS") == pytest.approx(650.0)
    assert _jan(m, "22222222", "COFINS") == pytest.approx(3000.0)
    assert _jan(m, "33333333", "PIS") == pytest.approx(1465.0 * 200000 / 210000)
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "rateio_pis_cofins_am", "valor"] = "nenhum"
    params.salvar("param_premissas", pr)
    m2 = as_is.carga_mensal(con_param)
    assert _jan(m2, "33333333", "PIS") == pytest.approx(1465.0)


def test_anualizacao(con_param):
    an = as_is.carga_anual(con_param)
    pis = an[(an.raiz == "22222222") & (an.tributo == "PIS")].iloc[0]
    assert pis["as_is"] == pytest.approx(650 * 3.3 / 3 * 12)
    assert pis["ajuste_reconciliacao"] == pytest.approx(0.0)


def test_r5_fecha_nas_fixtures(con_param):
    r5 = as_is.reconciliacao_r5(con_param)
    assert not r5.empty and r5["fecha"].all()
    assert set(r5["tributo"]) == {"ICMS", "IPI", "PIS", "COFINS"}


def test_saldos_credores(con_param):
    s = as_is.saldos_credores_finais(con_param).set_index("raiz")
    assert s.loc["22222222", "icms"] > 0     # Beta acumula saldo credor de ICMS
    assert s.loc["11111111", "icms"] == 0


def test_teses_nao_ativas_reduzem_as_is(con_param):
    t = params.carregar("param_teses")
    t.loc[0] = {"tese_id": "T1", "descricao": "Tese em discussão", "raiz_cnpj": "22222222", "tributo": "PIS",
                "tipo_efeito": "valor_fixo_mensal", "parametro": 100.0, "vigencia_ini": "2026-01",
                "vigencia_fim": "", "status": "em discussão"}
    t.loc[1] = {"tese_id": "T2", "descricao": "Tese ativa", "raiz_cnpj": "22222222", "tributo": "PIS",
                "tipo_efeito": "valor_fixo_mensal", "parametro": 999.0, "vigencia_ini": "2026-01",
                "vigencia_fim": "", "status": "ativa"}
    params.salvar("param_teses", t)
    sem = as_is.carga_anual(con_param, com_teses=False)
    com = as_is.carga_anual(con_param, com_teses=True)
    f = lambda a: a[(a.raiz == "22222222") & (a.tributo == "PIS")]["as_is"].iloc[0]  # noqa: E731
    assert f(sem) - f(com) == pytest.approx(100 * 12)  # so a tese nao ativa; ativa ja esta na apuracao
