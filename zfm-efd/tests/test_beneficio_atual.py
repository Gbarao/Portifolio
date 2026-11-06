"""Beneficio atual: valores calculados a mao nas fixtures (janeiro/2026).

Alfa (raiz 11111111), TIPI PROD01 = 15%, PROD02 = 5%:
  saidas incentivadas: 0001 PROD01 6101 400.000 (PIS 0,65 / COFINS 3) ; PROD01 5101 80.000 (0/0) ;
                       PROD02 5101 30.000 (0/0) ; 0002 PROD01 6101 150.000 (0,65/3)
  IPI    = (400.000 + 80.000 + 150.000) x 15% + 30.000 x 5%                = 96.000
  PIS    = 400.000 x 1% + 80.000 x 1,65% + 30.000 x 1,65% + 150.000 x 1%  =  7.315
  COFINS = 400.000 x 4,6% + 110.000 x 7,6% + 150.000 x 4,6%              = 33.660
  ICMS   = credito estimulo 38.500 - FTI 385                               = 38.115
Gama (33333333): so a filial do AM; matriz em SP fica fora.
  IPI 200.000 x 15% = 30.000 ; PIS 2.000 ; COFINS 9.200 ;
  ICMS = min(24.000 x 75%, 20.400) - 1% = 18.000 - 180 = 17.820
"""
from __future__ import annotations

import pytest

from zfm import beneficio_atual as ba
from zfm import params


def _jan(det, raiz):
    d = det[(det.raiz == raiz) & (det.mes == 1)]
    return d.groupby("tributo")["beneficio"].sum().round(2).to_dict()


def test_valores_calculados_a_mao(con_param):
    det = ba.calcular(con_param)
    assert _jan(det, "11111111") == {"IPI": 96000.0, "PIS": 7315.0, "COFINS": 33660.0, "ICMS": 38115.0}
    assert _jan(det, "22222222") == {"IPI": 5000.0, "PIS": 1000.0, "COFINS": 4600.0}
    assert _jan(det, "33333333") == {"IPI": 30000.0, "PIS": 2000.0, "COFINS": 9200.0, "ICMS": 17820.0}


def test_rastreabilidade(con_param):
    det = ba.calcular(con_param)
    assert det["arquivo_id"].notna().all() and det["linha_num"].notna().all()
    # cada linha de PIS aponta para um C181 existente
    pis = det[(det.tributo == "PIS") & (det.raiz == "11111111")]
    for a, l in pis[["arquivo_id", "linha_num"]].drop_duplicates().itertuples(index=False):
        assert con_param.execute("SELECT count(*) FROM raw_contrib_c181 WHERE arquivo_id = ? AND linha_num = ?",
                                 [int(a), int(l)]).fetchall()[0][0] == 1


def test_sem_tipi_gera_alerta_e_zero(con_param):
    from zfm import visoes
    pr = params.carregar("param_produtos")
    pr["aliq_tipi_2023"] = None
    params.salvar("param_produtos", pr)
    visoes.preparar(con_param)
    det = ba.calcular(con_param)
    ipi = det[det.tributo == "IPI"]
    assert ipi["beneficio"].sum() == 0
    assert ipi["observacao"].str.contains("TIPI").all()


def test_eliminar_intragrupo_reduz(con_param):
    a = ba.calcular(con_param)
    b = ba.calcular(con_param, eliminar_intragrupo=True)
    assert b[b.raiz == "11111111"]["beneficio"].sum() < a[a.raiz == "11111111"]["beneficio"].sum()
    assert b[b.raiz == "22222222"]["beneficio"].sum() == pytest.approx(a[a.raiz == "22222222"]["beneficio"].sum())


def test_teses(con_param):
    t = params.carregar("param_teses")
    t.loc[0] = {"tese_id": "T1", "descricao": "Tese sintética", "raiz_cnpj": "22222222", "tributo": "PIS",
                "tipo_efeito": "valor_fixo_mensal", "parametro": 1000.0, "vigencia_ini": "2026-02",
                "vigencia_fim": "", "status": "ativa"}
    params.salvar("param_teses", t)
    sem = ba.calcular(con_param)
    com = ba.calcular(con_param, com_teses=True)
    assert com["beneficio"].sum() - sem["beneficio"].sum() == pytest.approx(2000.0)  # fev e mar


def test_visao_so_entradas(con_param):
    e = ba.entradas_desoneradas(con_param)
    # Alfa jan: compras com PIS/COFINS suspenso (CST 72) = 0001: 100.000 + 20.000 + 50.000; 0002: 40.000
    pis = e[(e.raiz == "11111111") & (e.mes == 1) & (e.tributo == "PIS")]
    assert pis["valor_entradas"].sum() == pytest.approx(210000.0)
    assert pis["tributo_nao_cobrado_estimado"].sum() == pytest.approx(210000 * 0.0165)
    ipi = e[(e.raiz == "11111111") & (e.mes == 1) & (e.tributo == "IPI")]
    assert set(ipi["cst"]) == {"02", "05"}
