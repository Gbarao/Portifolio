"""Parametros: modelos, ida e volta do CSV, importacao, preenchimento automatico."""
from __future__ import annotations

import pandas as pd

from zfm import params
from zfm.cfop import classificar


def test_modelos_iniciais_de_aliquotas():
    a = params.carregar("param_aliquotas_cenario")
    assert set(a["cenario"]) == {"base", "baixo", "alto", "adverso"}
    base = a[a.cenario == "base"].set_index("ano")
    assert base.loc[2027, "aliq_cbs"] == 11.2 and base.loc[2027, "aliq_ibs"] == 0.1
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
    assert params.classificar_codigo("1234", "E116", "")[0] == "nao_classificado"
    assert params.classificar_codigo("1234", "E116", "", cod_or="000")[0] == "outros"
    assert params.classificar_codigo("AM009001", "E111", "Ajuste diverso")[0] == "nao_classificado"


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
    assert b.loc[2027, "aliq_cbs"] == 9.9 and b.loc[2027, "aliq_ibs"] == 0.1
    assert b.loc[2030, "aliq_ibs"] == 4.0 and b.loc[2033, "aliq_ibs"] == 20.0
    assert len(a[a.cenario == "novo"]) == 7


def test_resumo_lista_todas_as_premissas():
    r = params.resumo_premissas()
    assert {"Alíquotas CBS/IBS", "Transição", "Regime geral (fora da ZFM)", "Regras por cenário",
            "Premissas de cálculo", "Perímetro", "Método"} <= set(r["grupo"])
    chaves = set(r.loc[r.grupo == "Premissas de cálculo", "premissa"])
    assert {"prazo_cp_anos", "tratamento_nao_confirmados"} <= chaves
    legais = " ".join(r.loc[r.grupo == "Regras legais (LC 214/2025)", "premissa"])
    assert "ART447_DEMAIS" in legais and "ART450_IBS_FINAL" in legais and "ART454_LIMITE_TIPI" in legais


def test_premissa_nova_entra_em_arquivo_antigo():
    pr = params.carregar("param_premissas")
    params.salvar("param_premissas", pr[pr.chave != "tratamento_nao_confirmados"])
    assert "tratamento_nao_confirmados" in set(params.carregar("param_premissas")["chave"])
    # premissa obsoleta de versao anterior sai sozinha
    params.salvar("param_premissas", pd.concat([pr, pd.DataFrame([{"chave": "anualizacao", "valor": "x",
                                                                   "descricao": ""}])]))
    assert "anualizacao" not in set(params.carregar("param_premissas")["chave"])


def test_migracao_de_codigos_da_versao_anterior():
    # versao anterior gravava 'outros' para codigo sem regra
    df = pd.DataFrame([{"codigo": "X1", "registro": "E111", "classe": "outros", "descricao": "",
                        "regra_automatica": "sem regra", "revisado": False},
                       {"codigo": "X2", "registro": "E111", "classe": "outros", "descricao": "",
                        "regra_automatica": "sem regra", "revisado": True}])
    params.salvar("param_codigos_ajuste_icms", df)
    c = params.carregar("param_codigos_ajuste_icms").set_index("codigo")
    assert c.loc["X1", "classe"] == "nao_classificado"
    assert c.loc["X2", "classe"] == "outros"  # revisado pelo usuario: mantido


def test_devolucao_de():
    from zfm.cfop import devolucao_de
    assert devolucao_de("2201") == "venda_producao"
    assert devolucao_de("1202") == "venda_revenda"
    assert devolucao_de("6201") == "compra_industrializacao"
    assert devolucao_de("5202") == "compra_revenda"
    assert devolucao_de("5553") == "ativo"
    assert devolucao_de("6556") == "uso_consumo"
    assert devolucao_de("5101") == "" and devolucao_de("1556") == ""


def test_banco_de_versao_anterior_e_atualizado(con_carregado):
    """Banco criado por versao anterior (param_cfops sem 'devolucao_de') continua funcionando."""
    from zfm import visoes
    con_carregado.execute("DROP TABLE IF EXISTS param_cfops")
    con_carregado.execute("CREATE TABLE param_cfops (cfop VARCHAR, categoria VARCHAR, eh_receita BOOLEAN, "
                          "automatico BOOLEAN)")
    visoes.preparar(con_carregado)
    cols = [r[0] for r in con_carregado.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'param_cfops'").fetchall()]
    assert "devolucao_de" in cols
    assert con_carregado.execute("SELECT count(*) FROM v_base_operacoes").fetchall()[0][0] > 0


def test_aliquota_ipi_lida_da_efd(con_param):
    """A alíquota do IPI do produto vem da própria EFD (C170); produto revisado não é alterado."""
    raiz, cod = con_param.execute("""SELECT a.raiz, i.COD_ITEM FROM raw_contrib_c170 i
        JOIN raw_contrib_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
        JOIN arquivos a ON a.arquivo_id = i.arquivo_id WHERE d.IND_OPER = '1' LIMIT 1""").fetchall()[0]
    con_param.execute(f"UPDATE raw_contrib_c170 SET ALIQ_IPI = 9.75 WHERE COD_ITEM = '{cod}'")
    pr = params.carregar("param_produtos")
    m = (pr.raiz_cnpj == raiz) & (pr.cod_item == cod)
    pr.loc[m, ["aliq_ipi", "fonte_aliq_ipi", "revisado"]] = [None, "", False]
    params.salvar("param_produtos", pr)
    params.preencher_aliquota_ipi(con_param)
    pr = params.carregar("param_produtos").set_index(["raiz_cnpj", "cod_item"])
    assert pr.loc[(raiz, cod), "aliq_ipi"] == 9.75
    assert "C170 da EFD Contribuições" in pr.loc[(raiz, cod), "fonte_aliq_ipi"]
    # revisado pelo usuario: a EFD nao sobrescreve
    pr = pr.reset_index()
    pr.loc[(pr.raiz_cnpj == raiz) & (pr.cod_item == cod), ["aliq_ipi", "revisado"]] = [4.0, True]
    params.salvar("param_produtos", pr)
    params.preencher_aliquota_ipi(con_param)
    assert params.carregar("param_produtos").set_index(["raiz_cnpj", "cod_item"]).loc[(raiz, cod), "aliq_ipi"] == 4.0


def test_produtos_de_versao_anterior_sao_migrados():
    antigo = pd.DataFrame([{"raiz_cnpj": "11111111", "cod_item": "X", "aliq_tipi_2023": "15", "aliq_tipi_2026": "",
                            "classificacao_aprovada": "sim", "fonte": "manual", "motivo_exclusao": "bebida",
                            "projeto_cas_2022_2025": "sim", "produzido_zfm_2024": "nao", "incentivado": "sim"}])
    params.caminho("param_produtos").write_text(antigo.to_csv(sep=";", index=False), encoding="utf-8-sig")
    p = params.carregar("param_produtos").iloc[0]
    assert p["aliq_ipi"] == 15 and p["revisado"] and p["produzido_zfm_2024"]
    assert "bebida" in p["observacao"] and "versão anterior" in p["fonte_aliq_ipi"]
