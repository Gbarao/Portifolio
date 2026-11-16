"""Motor To Be e diferenca de carga, conferidos a mao.

Beta (22222222), premissa base_cbs_ibs = valor_liquido, cenario base:
  meses observados jan-mar (f = 1; 1,1; 1,2), anualizacao: soma de f no ano = 3,3 + 9 x 1,1 = 13,2
  saida mensal 100.000 x f para SP (interestadual), PROD02 TIPI 5% < 6,5%, produzido na ZFM:
  CP CBS de 6%. Entradas: 500.000 f de SP e 30.000 f da Alfa (ZFM), com aliquota zero.
  As Is (apuracao): ICMS 0 (saldo credor), IPI 0, PIS 650 f, COFINS 3.000 f
      PIS anual = 650 x 3,3 / 3 x 12 = 8.580 ; COFINS = 39.600
  2033: CBS = (11.300 f − 6.000 f) x 13,2 = 69.960 ; IBS = 0 (CP de entrada 447/449 > debito)
        diferenca = 69.960 − 48.180 = 21.780 (perda)
  2027: CBS = (11.200 f − 6.000 f) x 13,2 = 68.640 ; IBS teste 0,1% = 100 f x 13,2 = 1.320
        (sem CP de entrada nem art. 450 de IBS antes de 2029) ; diferenca = 69.960 − 48.180 = 21.780
  Vantagem competitiva: IPI do concorrente hoje = 100.000 f x 13,2 x 5% = 66.000; em 2033 = 0
"""
from __future__ import annotations

import pytest

from zfm import as_is, params, simulacao, visoes
from zfm.filtros import Filtro
from zfm.simulacao import Safras


def _premissa(chave, valor):
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == chave, "valor"] = valor
    params.salvar("param_premissas", pr)


def _linha(anual, raiz, ano, cenario="base"):
    return anual[(anual.raiz == raiz) & (anual.cenario == cenario) & (anual.ano == ano)].iloc[0]


def test_caso_simples_conferido_a_mao(con_param):
    _premissa("base_cbs_ibs", "valor_liquido")
    visoes.preparar(con_param)
    anual, _ = simulacao.simular(con_param)
    b = _linha(anual, "22222222", 2033)
    assert b["as_is_pis"] == pytest.approx(8580.0)
    assert b["as_is_cofins"] == pytest.approx(39600.0)
    assert b["as_is_icms"] == pytest.approx(0.0) and b["as_is_ipi"] == pytest.approx(0.0)
    assert b["debito_cbs"] == pytest.approx(11300 * 13.2)
    assert b["cp_cbs_gerado"] == pytest.approx(6000 * 13.2)
    assert b["to_be_cbs"] == pytest.approx(69960.0)
    assert b["to_be_ibs"] == pytest.approx(0.0)
    assert b["diferenca_total"] == pytest.approx(69960.0 - 48180.0)
    assert b["dif_pis"] == pytest.approx(-8580.0) and b["dif_cofins"] == pytest.approx(-39600.0)
    assert b["meses_saldo_credor"] == 12
    b27 = _linha(anual, "22222222", 2027)
    assert b27["to_be_cbs"] == pytest.approx(68640.0)
    assert b27["to_be_ibs"] == pytest.approx(1320.0)
    assert b27["cp_entrada_gerado"] == 0 and b27["cp_ibs_450"] == 0
    assert b27["diferenca_total"] == pytest.approx(21780.0)
    assert b["ipi_conc_as_is"] == pytest.approx(66000.0)
    assert b["ipi_conc_to_be"] == 0 and b["perda_vantagem_ipi"] == pytest.approx(66000.0)


def test_sinal_positivo_e_perda(con_param):
    anual, _ = simulacao.simular(con_param)
    a = anual.iloc[0]
    assert a["diferenca_total"] == pytest.approx(a["to_be_total"] - a["as_is_total"])


def test_ponte_fecha(con_param):
    anual, _ = simulacao.simular(con_param)
    for ano in (2027, 2030, 2033):
        p = simulacao.ponte(anual, "base", ano)
        inicio = p.loc[p.medida == "absolute", "valor"].sum()
        passos = p.loc[p.medida == "relative", "valor"].sum()
        fim = p.loc[p.medida == "total", "valor"].sum()
        assert inicio + passos == pytest.approx(fim)
        a = anual[(anual.cenario == "base") & (anual.ano == ano)]
        assert fim == pytest.approx(a["to_be_total"].sum())
        assert inicio == pytest.approx(a["as_is_total"].sum())


def test_icms_residual_segue_o_fator(con_param):
    anual, _ = simulacao.simular(con_param)
    alfa = anual[(anual.raiz == "11111111") & (anual.cenario == "base")].set_index("ano")
    asis = alfa.loc[2027, "as_is_icms"]
    assert alfa.loc[2028, "to_be_icms"] == pytest.approx(asis)
    assert alfa.loc[2029, "to_be_icms"] == pytest.approx(asis * 0.9)
    assert alfa.loc[2032, "to_be_icms"] == pytest.approx(asis * 0.6)
    assert alfa.loc[2033, "to_be_icms"] == 0
    assert (alfa["to_be_pis"] == 0).all() and (alfa["to_be_cofins"] == 0).all()


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
    assert b.loc[2029, "cp_entrada_expirado"] == 0
    assert b["cp_entrada_expirado"].sum() > 0
    m_fim = mensal[(mensal.raiz == "22222222") & (mensal.cenario == "base")].iloc[-1]
    assert b["cp_entrada_gerado"].sum() == pytest.approx(
        b["cp_entrada_usado"].sum() + b["cp_entrada_expirado"].sum() + m_fim["saldo_cp_ibs"])
    # teorico (todo CP aproveitado) <= realizavel
    assert b.loc[2033, "to_be_total_teorico"] <= b.loc[2033, "to_be_total"] + 1e-6


def test_cenario_adverso(con_param):
    anual, _ = simulacao.simular(con_param)
    adv = anual[anual.cenario == "adverso"]
    base = anual[anual.cenario == "base"]
    assert adv["cp_cbs_gerado"].sum() == 0 and adv["cp_ibs_450"].sum() == 0
    assert adv["ipi_conc_to_be"].sum() == 0
    assert base["cp_cbs_gerado"].sum() > 0
    assert adv["diferenca_total"].sum() > base["diferenca_total"].sum()  # mais perda


def test_parametro_alterado_muda_resultado(con_param):
    a1, _ = simulacao.simular(con_param)
    c = params.carregar("param_aliquotas_cenario")
    c.loc[(c.cenario == "base") & (c.ano == 2033), "aliq_cbs"] = 12.3
    params.salvar("param_aliquotas_cenario", c)
    a2, _ = simulacao.simular(con_param)
    f = lambda a: a[(a.cenario == "base") & (a.ano == 2033)]["debito_cbs"].sum()  # noqa: E731
    assert f(a2) > f(a1)


def test_ordem_de_deducao_do_ibs(con_param):
    a1, _ = simulacao.simular(con_param)
    _premissa("ordem_deducao_ibs", "debito-creditos-cp450-cp447_449")
    a2, _ = simulacao.simular(con_param)
    x1 = _linha(a1, "11111111", 2033)
    x2 = _linha(a2, "11111111", 2033)
    # art. 450 antes: incide sobre o saldo antes do CP de entrada (base maior)
    assert x2["cp_ibs_450"] > x1["cp_ibs_450"]
    assert x2["to_be_ibs"] >= 0 and x1["to_be_ibs"] >= 0


def test_nivel_de_apuracao_por_estabelecimento(con_param):
    a1, _ = simulacao.simular(con_param)
    _premissa("nivel_apuracao_cbs_ibs", "estabelecimento")
    a2, _ = simulacao.simular(con_param)
    x1 = _linha(a1, "11111111", 2033)
    x2 = _linha(a2, "11111111", 2033)
    # sem compensacao entre estabelecimentos, a carga nao pode ser menor
    assert x2["to_be_cbs"] >= x1["to_be_cbs"] - 1e-6
    assert x2["as_is_total"] == pytest.approx(x1["as_is_total"])
    assert x2["debito_cbs"] == pytest.approx(x1["debito_cbs"])


def test_devolucoes_abatem_a_base(con_param):
    _premissa("base_cbs_ibs", "valor_liquido")
    i1 = simulacao.insumos_mensais(con_param)
    _premissa("abater_devolucoes", "nao")
    visoes.preparar(con_param)  # premissas lidas pelas visoes vem do banco (a tela sincroniza sozinha)
    i2 = simulacao.insumos_mensais(con_param)
    g = lambda i, c: i[(i.raiz == "11111111") & (i.mes == 2)][c].sum()  # noqa: E731
    # devolucao de venda 2201 de 40.000 (interestadual) e devolucao de compra 6201 de 10.000 de SP
    assert g(i2, "deb_base_zfm") - g(i1, "deb_base_zfm") == pytest.approx(40000.0)
    assert g(i2, "cp447_cheio") - g(i1, "cp447_cheio") == pytest.approx(10000 * 0.075)


def test_filtro_de_periodo_anualiza_pelos_meses_do_filtro(con_param):
    an = as_is.carga_anual(con_param, Filtro(mes_ini=1, mes_fim=1))
    pis = an[(an.raiz == "22222222") & (an.tributo == "PIS")]["as_is"].iloc[0]
    assert pis == pytest.approx(650 * 12)


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


def test_percentuais_vem_das_premissas(con_param):
    _premissa("p_cbs_450_ipi_zerado", "5")
    assert simulacao.p_cbs_450(5.0, True, False) == pytest.approx(0.05)


def test_composicao_saidas_mais_entradas_igual_carga(con_param):
    anual, _ = simulacao.simular(con_param)
    sel = anual[(anual.cenario == "base") & (anual.ano == 2033)]
    comp = simulacao.composicao(sel, con_param)
    tb = comp[comp.regime == "To Be"].groupby("raiz")["valor"].sum()
    for r in sel.itertuples():
        assert tb.get(r.raiz, 0.0) == pytest.approx(r.to_be_total, abs=0.01)
    ai = comp[comp.regime == "As Is"].groupby("raiz")["valor"].sum()
    for r in sel.itertuples():
        assert ai.get(r.raiz, 0.0) == pytest.approx(r.as_is_total, abs=0.01)
