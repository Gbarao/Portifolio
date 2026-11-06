"""Simulacao: caso simples conferido a mao, absorcao com expiracao, cenario adverso.

Beta (22222222), premissa base_cbs_ibs = valor_liquido, cenario base, 2033
(CBS 11,3%, IBS 18,7%, fator ICMS 0, fator CP entrada 1):
  saida mensal 100.000 x f (f = 1; 1,1; 1,2 em jan-mar; media 1,1 nos demais) -> soma de f = 13,2
  PROD02: TIPI 5% < 6,5% e produzido na ZFM -> CP CBS de 6%
  CBS: debito 11.300 f ; credito 0 (entradas com aliquota zero) ; CP 6.000 f ; a pagar 5.300 f
       -> cbs_pagar = 69.960 ; beneficio CBS = 6.000 x 13,2 = 79.200
  IBS: debito 18.700 f ; CP de entrada 447 (500.000 f x 7,5%) + 449 (30.000 f x 7,5%) > debito
       -> ibs_pagar = 0 ; beneficio IBS = 18.700 x 13,2 = 246.840 ; saldo credor estrutural
"""
from __future__ import annotations

import pytest

from zfm import params, simulacao, visoes
from zfm.simulacao import Safras


def _premissa(chave, valor):
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == chave, "valor"] = valor
    params.salvar("param_premissas", pr)


def test_caso_simples_conferido_a_mao(con_param):
    _premissa("base_cbs_ibs", "valor_liquido")
    visoes.preparar(con_param)
    anual, mensal = simulacao.simular(con_param)
    b = anual[(anual.raiz == "22222222") & (anual.cenario == "base") & (anual.ano == 2033)].iloc[0]
    assert b["debito_cbs"] == pytest.approx(11300 * 13.2)
    assert b["cp_cbs_gerado"] == pytest.approx(6000 * 13.2)
    assert b["cbs_pagar"] == pytest.approx(69960.0)
    assert b["beneficio_cbs"] == pytest.approx(79200.0)
    assert b["ibs_pagar"] == pytest.approx(0.0)
    assert b["beneficio_ibs"] == pytest.approx(18700 * 13.2)
    assert b["meses_saldo_credor"] == 12
    # 2027: CBS 11,2%, sem IBS
    b27 = anual[(anual.raiz == "22222222") & (anual.cenario == "base") & (anual.ano == 2027)].iloc[0]
    assert b27["debito_cbs"] == pytest.approx(11200 * 13.2)
    assert b27["debito_ibs"] == 0
    # beneficio de hoje anualizado = media mensal x 12
    from zfm import beneficio_atual as ba
    det = ba.calcular(con_param)
    hoje_ytd = det[det.raiz == "22222222"]["beneficio"].sum()
    assert b["beneficio_hoje"] == pytest.approx(hoje_ytd / 3 * 12)
    assert b["delta"] == pytest.approx(b["beneficio_pos"] - b["beneficio_hoje"])


def test_safras_expiram_no_quinto_ano():
    s = Safras(prazo_meses=60)
    s.adicionar(0, 100.0)
    s.adicionar(12, 50.0)
    assert s.expirar(59) == 0
    assert s.usar(30) == 30          # usa primeiro a safra mais antiga
    assert s.expirar(60) == pytest.approx(70.0)
    assert s.saldo == pytest.approx(50.0)
    assert s.expirar(72) == pytest.approx(50.0)


def test_absorcao_com_expiracao(con_param):
    _premissa("prazo_cp_anos", "1")
    anual, mensal = simulacao.simular(con_param)
    b = anual[(anual.raiz == "22222222") & (anual.cenario == "base")].set_index("ano")
    assert b.loc[2029, "cp_entrada_expirado"] == 0   # nada vence no 1o ano
    assert b["cp_entrada_expirado"].sum() > 0         # safras nao usadas em 12 meses expiram
    # conservacao: gerado = usado + expirado + saldo final
    m_fim = mensal[(mensal.raiz == "22222222") & (mensal.cenario == "base")].iloc[-1]
    assert b["cp_entrada_gerado"].sum() == pytest.approx(
        b["cp_entrada_usado"].sum() + b["cp_entrada_expirado"].sum() + m_fim["saldo_cp_ibs"])
    assert (b["cp_entrada_gerado"] >= b["cp_entrada_usado"]).all()
    assert b.loc[2033, "beneficio_ibs_teorico"] >= b.loc[2033, "beneficio_ibs"]
    m = mensal[(mensal.raiz == "22222222") & (mensal.cenario == "base")]
    assert m["saldo_cp_ibs"].max() > 0


def test_cenario_adverso_zera_cp_450(con_param):
    anual, _ = simulacao.simular(con_param)
    adv = anual[anual.cenario == "adverso"]
    base = anual[anual.cenario == "base"]
    assert adv["cp_cbs_gerado"].sum() == 0 and adv["cp_ibs_450"].sum() == 0
    assert adv["beneficio_ipi"].sum() == 0
    assert base["cp_cbs_gerado"].sum() > 0
    assert adv["beneficio_pos"].sum() < base["beneficio_pos"].sum()


def test_parametro_alterado_muda_resultado(con_param):
    a1, _ = simulacao.simular(con_param)
    c = params.carregar("param_aliquotas_cenario")
    c.loc[(c.cenario == "base") & (c.ano == 2033), "aliq_cbs"] = 12.3
    params.salvar("param_aliquotas_cenario", c)
    a2, _ = simulacao.simular(con_param)
    f = lambda a: a[(a.cenario == "base") & (a.ano == 2033)]["debito_cbs"].sum()  # noqa: E731
    assert f(a2) > f(a1)


def test_percentuais_art_450():
    assert simulacao.p_ibs_450("final", False) == 0.55
    assert simulacao.p_ibs_450("capital", False) == 0.75
    assert simulacao.p_ibs_450("intermediario", False) == 0.9025
    assert simulacao.p_ibs_450("final", True) == 1.0
    assert simulacao.p_ibs_450("informatica", False) == 1.0
    assert simulacao.p_cbs_450(5.0, True, False) == 0.06
    assert simulacao.p_cbs_450(5.0, True, True) == 0.02
    assert simulacao.p_cbs_450(15.0, True, False) == 0.02
    assert simulacao.p_cbs_450(None, True, False) == 0.02


def test_ponte_fecha(con_param):
    anual, _ = simulacao.simular(con_param)
    p = simulacao.ponte(anual, "base", 2033)
    inicio = p.loc[p.medida == "absolute", "valor"].sum()
    passos = p.loc[p.medida == "relative", "valor"].sum()
    fim = p.loc[p.medida == "total", "valor"].sum()
    assert inicio + passos == pytest.approx(fim)


def test_visao_saidas_mais_entradas_igual_total(con_param):
    anual, _ = simulacao.simular(con_param)
    assert (anual["beneficio_saidas"] + anual["beneficio_entradas"]).round(4).equals(
        anual["beneficio_pos"].round(4))
    b = anual[(anual.raiz == "22222222") & (anual.cenario == "base") & (anual.ano == 2033)].iloc[0]
    assert b["beneficio_entradas"] == pytest.approx(b["cp_entrada_usado"])
    assert b["beneficio_entradas"] > 0


def test_percentuais_vem_das_premissas(con_param):
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "p_cbs_450_ipi_zerado", "valor"] = "5"
    params.salvar("param_premissas", pr)
    assert simulacao.p_cbs_450(5.0, True, False) == pytest.approx(0.05)
