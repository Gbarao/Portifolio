"""Parametros: modelos, ida e volta do CSV, importacao, preenchimento automatico."""
from __future__ import annotations

import pandas as pd

from zfm import params
from zfm.cfop import classificar


def test_modelos_iniciais_de_aliquotas():
    a = params.carregar("param_aliquotas_cenario")
    assert set(a["cenario"]) == {"base", "baixo", "alto", "adverso"}
    base = a[a.cenario == "base"].set_index("ano")
    assert base.loc[2027, "aliq_cbs"] == 11.2 and base.loc[2027, "aliq_ibs"] == 0
    assert base.loc[2033, "aliq_cbs"] == 11.3 and base.loc[2033, "aliq_ibs"] == 18.7
    assert base.loc[2029, "fator_icms"] == 0.9
    assert abs(base.loc[2029, "aliq_ibs"] - 1.87) < 1e-9
    adv = a[a.cenario == "adverso"]
    assert not adv["aplica_cp_450"].any()


def test_csv_ida_e_volta_com_virgula(tmp_path):
    df = params.carregar("param_aliquotas_regime_geral")
    params.salvar("param_aliquotas_regime_geral", df)
    txt = params.caminho("param_aliquotas_regime_geral").read_bytes()
    assert txt.startswith(b"\xef\xbb\xbf") and b"1,65" in txt and b";" in txt
    de_novo = params.carregar("param_aliquotas_regime_geral")
    assert de_novo.set_index("tributo").loc["PIS", "aliquota"] == 1.65


def test_importar_csv_do_excel():
    conteudo = "tributo;aliquota;observacao\r\nPIS;2,1;teste\r\nCOFINS;9,65;\r\n".encode("latin-1")
    df = params.importar_csv("param_aliquotas_regime_geral", conteudo)
    assert df.set_index("tributo").loc["COFINS", "aliquota"] == 9.65


def test_importar_csv_sem_coluna_chave():
    import pytest
    with pytest.raises(ValueError):
        params.importar_csv("param_aliquotas_regime_geral", b"x;y\n1;2\n")


def test_classificacao_de_codigos():
    assert params.classificar_codigo("AM040014", "E111", "")[0] == "credito_estimulo"
    assert params.classificar_codigo("AM040099", "E111", "")[0] == "credito_estimulo"
    assert params.classificar_codigo("AM020005", "E111", "Crédito estímulo Lei 2826")[0] == "credito_estimulo"
    assert params.classificar_codigo("9999", "E116", "Contribuição FMPES")[0] == "fundo_FMPES"
    assert params.classificar_codigo("9998", "E116", "Recolhimento UEA")[0] == "fundo_UEA"
    assert params.classificar_codigo("1234", "E116", "")[0] == "outros"


def test_classificacao_cfop():
    assert classificar("6101") == ("venda_producao", True)
    assert classificar("5102") == ("venda_revenda", True)
    assert classificar("5152") == ("transferencia", False)
    assert classificar("6949") == ("remessa_retorno", False)
    assert classificar("2101") == ("compra_industrializacao", False)
    assert classificar("1556") == ("uso_consumo", False)
    assert classificar("2551") == ("ativo", False)
    assert classificar("1202") == ("devolucao", False)


def test_preencher_nao_apaga_edicao(con_carregado):
    from zfm import visoes
    visoes.preparar(con_carregado)
    n = params.preencher_a_partir_das_efds(con_carregado)
    assert n["param_empresas"] == 3 and n["param_codigos_ajuste_icms"] >= 2
    cod = params.carregar("param_codigos_ajuste_icms").set_index("codigo")
    assert cod.loc["AM040014", "classe"] == "credito_estimulo"
    assert cod.loc["FTI9", "classe"] == "fundo_FTI"
    pr = params.carregar("param_produtos").set_index(["raiz_cnpj", "cod_item"])
    assert pr.loc[("11111111", "PROD01"), "incentivado"]
    assert not pr.loc[("11111111", "INS01"), "incentivado"]
    assert pr.loc[("11111111", "PROD02"), "tipo_bem"] == "intermediario"
    # edicao do usuario preservada
    c = params.carregar("param_codigos_ajuste_icms")
    c.loc[c.codigo == "AM040014", "classe"] = "outros_beneficios"
    params.salvar("param_codigos_ajuste_icms", c)
    n2 = params.preencher_a_partir_das_efds(con_carregado)
    assert n2["param_codigos_ajuste_icms"] == 0
    c2 = params.carregar("param_codigos_ajuste_icms").set_index("codigo")
    assert c2.loc["AM040014", "classe"] == "outros_beneficios"


def test_aplicar_aliquotas_de_referencia():
    refs = params.aliquotas_referencia()
    assert set(refs["cenario"]) == {"base", "baixo", "alto", "adverso"}
    refs.loc[refs.cenario == "base", ["cbs_referencia", "ibs_referencia"]] = [10.0, 20.0]
    refs.loc[len(refs)] = {"cenario": "novo", "cbs_referencia": 9.0, "ibs_referencia": 17.0,
                           "aplica_cp_450": True, "ipi_protegido_override": "", "fonte": "teste"}
    params.aplicar_referencias(refs)
    a = params.carregar("param_aliquotas_cenario")
    b = a[a.cenario == "base"].set_index("ano")
    assert b.loc[2027, "aliq_cbs"] == 9.9 and b.loc[2027, "aliq_ibs"] == 0
    assert b.loc[2030, "aliq_ibs"] == 4.0 and b.loc[2033, "aliq_ibs"] == 20.0
    assert len(a[a.cenario == "novo"]) == 7


def test_resumo_lista_todas_as_premissas():
    r = params.resumo_premissas()
    assert {"Alíquotas CBS/IBS", "Transição", "Regime geral (fora da ZFM)", "Entradas pós-reforma",
            "Premissas de cálculo", "Perímetro", "Método"} <= set(r["grupo"])
    chaves = set(r.loc[r.grupo == "Premissas de cálculo", "premissa"])
    assert {"prazo_cp_anos", "limite_tipi_ipi", "cp447_demais_e_es", "p_ibs_450_final"} <= chaves


def test_premissa_nova_entra_em_arquivo_antigo():
    pr = params.carregar("param_premissas")
    params.salvar("param_premissas", pr[pr.chave != "cp449"])
    assert "cp449" in set(params.carregar("param_premissas")["chave"])
