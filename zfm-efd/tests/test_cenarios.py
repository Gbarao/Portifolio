"""Cenarios ZFM (C1-C5): classificacao, As Is x To Be por cenario, IPI por produto e alertas."""
from __future__ import annotations

import pytest

from zfm import cenarios, params, simulacao, visoes


def _tipo(cnpj, tipo=None, regime=None):
    ez = params.carregar("param_empresas_zfm")
    if tipo:
        ez.loc[ez.cnpj == cnpj, "tipo"] = tipo
    if regime:
        ez.loc[ez.cnpj == cnpj, "regime"] = regime
    params.salvar("param_empresas_zfm", ez)


def _matriz(con):
    m = cenarios.matriz(con)
    return m.groupby(["raiz", "cenario"])["valor"].sum().round(2).to_dict()


def test_empresas_zfm_pre_preenchidas(con_param):
    ez = params.carregar("param_empresas_zfm").set_index("cnpj")
    for c in ("11111111000191", "11111111000272", "22222222000122", "33333333000214"):
        assert ez.loc[c, "tipo"] == "industria_incentivada" and ez.loc[c, "origem"] == "grupo"
    assert ez.loc["77777777000177", "tipo"] == "habilitado"      # cliente de Manaus com SUFRAMA
    assert "33333333000133" not in ez.index                       # matriz em SP fica fora


def test_classificacao_das_fixtures(con_param):
    m = _matriz(con_param)
    assert m[("11111111", "C1a")] == 165000.0                    # importação 50.000 f x 3,3
    assert m[("22222222", "C3a")] == 99000.0                     # intermediário da Alfa para a Beta
    assert m[("11111111", "C4d")] == pytest.approx(27000.0)      # PROD02 da Alfa para a Beta (rateado)
    assert m[("33333333", "C4a")] == 660000.0
    assert m[("11111111", "TR")] == 10000.0                      # transferência (saída + entrada)
    assert not any(k[1].startswith("NC") for k in m)             # nada sem classificação
    # devoluções caem no cenário de origem, com valor negativo
    d = con_param.execute("""SELECT cfop, cenario, valor FROM v_cenarios
                             WHERE natureza LIKE 'devolucao%' ORDER BY cfop""").fetchall()
    assert d == [("2201", "C4a", -40000.0), ("6201", "C2a", -10000.0)]


def test_habilitado_regular_simples_e_nao_habilitado(con_param):
    _tipo("22222222000122", "habilitado")
    visoes.preparar(con_param)
    assert _matriz(con_param)[("22222222", "C2b")] == 1650000.0
    _tipo("22222222000122", regime="simples")
    visoes.preparar(con_param)
    assert _matriz(con_param)[("22222222", "C2c")] == 1650000.0
    _tipo("22222222000122", "nao_habilitado")
    visoes.preparar(con_param)
    m = _matriz(con_param)
    assert ("22222222", "NC_E") in m and ("22222222", "NC_S") in m
    mot = {r[0] for r in con_param.execute("""SELECT DISTINCT motivo FROM v_cenarios
                                              WHERE raiz = '22222222' AND cenario LIKE 'NC%'""").fetchall()}
    assert any("Empresas ZFM" in x for x in mot)


def test_c3b_e_c1c(con_param):
    _tipo("11111111000191", "habilitado")     # Alfa 0001 vira comércio: importação para industrialização = C1c
    visoes.preparar(con_param)
    m = _matriz(con_param)
    assert m[("11111111", "C1c")] == 165000.0
    assert m[("22222222", "C3b")] == 99000.0  # Beta compra de fornecedor habilitado (não indústria)


def test_c4b_consumidor_final(con, pasta_efd):
    """Cliente de SP sem IE (não contribuinte): vendas para fora da ZFM viram C4b."""
    from zfm.parsers import carregar_arquivo
    for p in pasta_efd.glob("*.txt"):
        t = p.read_bytes().decode("latin-1").replace("|66666666000166||333333333333|", "|66666666000166|||")
        p.write_bytes(t.encode("latin-1"))
    for p in sorted(pasta_efd.glob("*.txt")):
        carregar_arquivo(con, p)
    visoes.preparar(con)
    params.preencher_a_partir_das_efds(con)
    m = _matriz(con)
    assert m[("33333333", "C4b")] == 660000.0 and ("33333333", "C4a") not in m


def test_soma_dos_cenarios_igual_ao_total(con_param):
    anual, _ = simulacao.simular(con_param)
    r = cenarios.resultado(con_param, anual)
    for ano in (2027, 2030, 2033):
        x = r[(r.cenario_aliq == "base") & (r.ano == ano)].groupby("raiz")[["as_is", "to_be", "diferenca"]].sum()
        e = anual[(anual.cenario == "base") & (anual.ano == ano)].set_index("raiz")
        for raiz in e.index:
            assert x.loc[raiz, "as_is"] == pytest.approx(e.loc[raiz, "as_is_total"], abs=0.01)
            assert x.loc[raiz, "to_be"] == pytest.approx(e.loc[raiz, "to_be_total"], abs=0.01)
            assert x.loc[raiz, "diferenca"] == pytest.approx(e.loc[raiz, "diferenca_total"], abs=0.01)


def test_to_be_por_cenario_conferido_a_mao(con_param):
    """Beta, valor_liquido, 2033: C4a CBS = (11,3% − 6%) x 100.000 x 13,2 = 69.960 (sem saldo credor)."""
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "base_cbs_ibs", "valor"] = "valor_liquido"
    params.salvar("param_premissas", pr)
    visoes.preparar(con_param)
    anual, _ = simulacao.simular(con_param)
    r = cenarios.resultado(con_param, anual)
    x = r[(r.cenario_aliq == "base") & (r.ano == 2033) & (r.raiz == "22222222")].set_index(["cenario", "tributo"])
    assert x.loc[("C4a", "CBS"), "to_be"] == pytest.approx(69960.0)
    # CP 447 de entrada (C2a) e 449 (C3a) aparecem como redução do IBS
    assert x.loc[("C2a", "IBS"), "to_be"] == pytest.approx(-500000 * 13.2 * 0.075)
    assert x.loc[("C3a", "IBS"), "to_be"] == pytest.approx(-30000 * 13.2 * 0.075)
    # As Is de PIS da venda C4a = 650 f anualizado
    assert x.loc[("C4a", "PIS"), "as_is"] == pytest.approx(8580.0)


def test_ipi_por_produto(con_param):
    d = cenarios.ipi_por_produto(con_param).set_index(["raiz", "cod_item"])
    assert "mantido" in d.loc[("11111111", "PROD01"), "classe_ipi"]
    assert "zero para todos" in d.loc[("22222222", "PROD02"), "classe_ipi"]
    assert d.loc[("22222222", "PROD02"), "perda_vantagem"] == pytest.approx(66000.0)
    assert d.loc[("22222222", "PROD02"), "cp_cbs_pct"] == pytest.approx(6.0)
    assert (d["carga_propria_ipi"] == 0).all()
    assert d.loc[("22222222", "PROD02"), "comprador_perde_credito_ipi"]


def test_alertas(con_param):
    a = cenarios.alertas(con_param)
    assert set(a["tipo"]) >= {"Comprovação de ingresso (risco)", "Tipo ZFM definido automaticamente"}
    assert "Divergência CST/alíquota" not in set(a["tipo"])
    # conferência: exigir PIS de 1,3% nas vendas C4a -> vendas a 0,65% viram alerta
    c = params.carregar("param_conferencia_cenario")
    c.loc[(c.cenarios == "C4a;C4b") & (c.tributo == "PIS"), "valores"] = "1,3"
    params.salvar("param_conferencia_cenario", c)
    visoes.preparar(con_param)
    conf = cenarios.conferencias(con_param)
    assert set(conf["raiz"]) == {"11111111", "22222222", "33333333"}
    # produto com crédito estímulo acima do art. 450 vira candidato a perda
    pr = params.carregar("param_produtos")
    pr.loc[(pr.raiz_cnpj == "11111111") & (pr.cod_item == "PROD01"), "nivel_credito_estimulo"] = 90.0
    params.salvar("param_produtos", pr)
    a2 = cenarios.alertas(con_param)
    assert "Produto candidato a perda no IBS" in set(a2["tipo"])
