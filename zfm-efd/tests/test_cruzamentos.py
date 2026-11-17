"""Cruzamentos EFD ICMS/IPI × EFD Contribuicoes e cobertura das escrituracoes.

Base sintetica: Alfa e Beta com EFD Contribuicoes consolidada (C180), Gama detalhada (C100/C170):
os 6 documentos da Gama (3 saidas e 3 entradas no estabelecimento 0214) estao nas duas EFDs.
"""
from __future__ import annotations

import pytest

from zfm import conciliacoes, cruzamentos as cz, visoes


def _gama_doc(con, sentido="1"):
    return con.execute(f"""SELECT d.arquivo_id, d.linha_num, d.CHV_NFE FROM raw_contrib_c100 d
                           WHERE d.cnpj_estab = '33333333000214' AND d.IND_OPER = '{sentido}'
                           ORDER BY 1, 2 LIMIT 1""").fetchall()[0]


def test_base_limpa_sem_divergencias(con_param):
    for k in ("Q7", "Q14", "Q15", "Q17"):
        assert conciliacoes.CHECAGENS[k][1](con_param).empty, k
    r = cz.resumo_pareamento(con_param)
    gama = r[(r.raiz == "33333333") & (r.situacao == cz.NAS_DUAS)]
    assert gama["documentos"].sum() == 12  # 6 documentos × 2 fontes
    # Alfa/Beta: Contribuicoes consolidada -> documentos da Fiscal sem par por natureza
    assert set(r[r.raiz == "11111111"]["situacao"]) == {cz.CONSOLIDADA}


def test_transferencia_nao_e_repeticao(con_param):
    # a NF-e de transferencia 0191 -> 0272 aparece como saida e como entrada na Fiscal da Alfa
    assert conciliacoes.CHECAGENS["Q16"][1](con_param).empty


def test_documento_so_na_fiscal(con_param):
    aid, linha, chave = _gama_doc(con_param)
    con_param.execute("DELETE FROM raw_contrib_c170 WHERE arquivo_id = ? AND pai_linha = ?", [aid, linha])
    con_param.execute("DELETE FROM raw_contrib_c100 WHERE arquivo_id = ? AND linha_num = ?", [aid, linha])
    visoes.preparar(con_param, forcar=True)
    q7 = conciliacoes.CHECAGENS["Q7"][1](con_param)
    assert list(q7["problema"]) == [cz.SO_FISCAL]
    assert q7["chv_nfe"].iloc[0] == chave


def test_valor_diferente_e_cfop_diferente(con_param):
    aid, linha, _ = _gama_doc(con_param)
    con_param.execute("UPDATE raw_contrib_c100 SET VL_DOC = VL_DOC + 100 WHERE arquivo_id = ? AND linha_num = ?",
                      [aid, linha])
    con_param.execute("UPDATE raw_contrib_c170 SET CFOP = '5949' WHERE arquivo_id = ? AND pai_linha = ?", [aid, linha])
    q7 = conciliacoes.CHECAGENS["Q7"][1](con_param)
    assert len(q7) == 1 and "valor do documento" in q7["problema"].iloc[0]
    q15 = conciliacoes.CHECAGENS["Q15"][1](con_param)
    assert {"CFOP só na EFD ICMS/IPI (C190)", "CFOP só na EFD Contribuições (C170)"} <= set(q15["problema"])


def test_documento_repetido_em_outro_periodo(con_param):
    # copia um documento de saida da Gama de jan para o arquivo de fev da mesma EFD Fiscal
    arqs = con_param.execute("""SELECT arquivo_id FROM arquivos WHERE tipo = 'ICMS_IPI' AND cnpj = '33333333000214'
                                ORDER BY dt_ini""").fetchall()
    jan, fev = arqs[0][0], arqs[1][0]
    con_param.execute(f"""INSERT INTO raw_icms_c100 SELECT * REPLACE ({fev} AS arquivo_id, linha_num + 900000 AS linha_num)
                          FROM raw_icms_c100 WHERE arquivo_id = {jan} AND IND_OPER = '1' LIMIT 1""")
    q16 = conciliacoes.CHECAGENS["Q16"][1](con_param)
    assert sorted(q16["situacao"]) == ["Primeira ocorrência", "Repetição"]
    r = cz.resumo_pareamento(con_param)
    assert r[r.situacao == cz.REPETIDO]["documentos"].sum() == 1


def test_cobertura_aponta_escrituracao_faltando(con_param):
    con_param.execute("""UPDATE arquivos SET ativo = FALSE WHERE tipo = 'CONTRIB' AND raiz = '22222222'
                         AND month(dt_ini) = 2""")
    con_param.execute("""UPDATE arquivos SET ativo = FALSE WHERE tipo = 'ICMS_IPI' AND cnpj = '11111111000272'
                         AND month(dt_ini) = 3""")
    visoes.preparar(con_param)
    f = cz.faltas(cz.cobertura_banco(con_param))
    got = {(r.cnpj_estab, r.mes, r.situacao) for r in f.itertuples()}
    assert got == {("22222222000122", 2, "Falta EFD Contribuições"),
                   ("11111111000272", 3, "Falta EFD ICMS/IPI")}
    assert not conciliacoes.CHECAGENS["Q17"][1](con_param).empty


def test_cobertura_antes_de_importar(tmp_path):
    from tests.fixtures.gerador import gerar_conjunto
    pasta = tmp_path / "efd"
    gerar_conjunto(pasta)
    (pasta / "EFD_ICMS_IPI_33333333000214_202602.txt").unlink()
    escs = [cz.identificar_rapido(p) for p in sorted(pasta.glob("*.txt"))]
    contrib_gama = [e for e in escs if e.tipo == "CONTRIB" and e.raiz == "33333333"][0]
    assert {c for c, *_ in contrib_gama.estabs} == {"33333333000133", "33333333000214"}
    f = cz.faltas(cz.cobertura(escs))
    assert {(r.cnpj_estab, r.mes, r.situacao) for r in f.itertuples()} == {
        ("33333333000214", 2, "Falta EFD ICMS/IPI")}


def test_c170_x_c190(con_param):
    aid, linha = con_param.execute("""SELECT c.arquivo_id, c.pai_linha FROM raw_icms_c170 c
                                      JOIN arquivos a USING (arquivo_id) WHERE a.ativo LIMIT 1""").fetchall()[0]
    con_param.execute("UPDATE raw_icms_c170 SET VL_ICMS = VL_ICMS + 50 WHERE arquivo_id = ? AND pai_linha = ?",
                      [aid, linha])
    q14 = conciliacoes.CHECAGENS["Q14"][1](con_param)
    assert len(q14) >= 1 and (q14["icms_c170"] - q14["icms_c190"]).abs().max() >= 50 - 1e-6


# ---------------------------------------------------------------------------
# Cruzamento de PIS/COFINS das entradas (mecanica do sped_analytics_app)
# Gama (detalhada): 3 entradas por mes, 1 item cada (INS01, CFOP 2101); o PIS e posto em 100 para rastrear.
# ---------------------------------------------------------------------------
def _gama_entradas(con, pis=100.0):
    con.execute(f"""UPDATE raw_contrib_c170 SET VL_PIS = {pis}, VL_COFINS = {pis * 4.6}, CST_PIS = '50', CST_COFINS = '50'
                    WHERE (arquivo_id, pai_linha) IN (SELECT arquivo_id, linha_num FROM raw_contrib_c100
                                                      WHERE cnpj_estab = '33333333000214' AND IND_OPER = '0')""")
    return con.execute("""SELECT i.arquivo_id, i.linha_num, i.pai_linha, a.dt_ini FROM raw_contrib_c170 i
                          JOIN raw_contrib_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
                          JOIN arquivos a ON a.arquivo_id = i.arquivo_id
                          WHERE d.cnpj_estab = '33333333000214' AND d.IND_OPER = '0' ORDER BY a.dt_ini""").fetchall()


def _gama(con):
    return con.execute("""SELECT mes, reg_origem, nivel_cruzamento, cod_item, valor, vl_pis, vl_cofins FROM v_entradas_item
                          WHERE cnpj_estab = '33333333000214' ORDER BY mes, nivel_cruzamento""").df()


def _fecha(con):
    assert conciliacoes.CHECAGENS["Q18"][1](con).empty
    efd = con.execute("""SELECT sum(i.VL_PIS) FROM raw_contrib_c170 i JOIN raw_contrib_c100 d
                         ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
                         WHERE d.IND_OPER = '0' AND d.cnpj_estab = '33333333000214'""").fetchall()[0][0]
    base = con.execute("SELECT sum(vl_pis) FROM v_entradas_item WHERE cnpj_estab = '33333333000214'").fetchall()[0][0]
    assert float(efd) == pytest.approx(base)


def test_n1_item_a_item_e_fechamento(con_param):
    _gama_entradas(con_param)
    visoes.preparar(con_param, forcar=True)
    g = _gama(con_param)
    assert set(g["nivel_cruzamento"]) == {"N1_ITEM"} and (g["vl_pis"] == 100).all()
    _fecha(con_param)


def test_codigo_diferente_na_mesma_posicao_vira_n1v(con_param):
    aid, linha, *_ = _gama_entradas(con_param)[0]
    con_param.execute("UPDATE raw_contrib_c170 SET COD_ITEM = 'OUTRO' WHERE arquivo_id = ? AND linha_num = ?", [aid, linha])
    visoes.preparar(con_param, forcar=True)
    g = _gama(con_param)
    assert g.loc[g.mes == 1, "nivel_cruzamento"].tolist() == ["N1V_POSICAO_VALOR"]
    assert g.loc[g.mes == 1, "vl_pis"].iloc[0] == 100
    q15 = conciliacoes.CHECAGENS["Q15"][1](con_param)
    assert q15["problema"].str.contains("código INS01 × OUTRO").any()
    _fecha(con_param)


def test_numeracao_diferente_casa_por_codigo_e_cfop(con_param):
    aid, linha, *_ = _gama_entradas(con_param)[0]
    con_param.execute("UPDATE raw_contrib_c170 SET NUM_ITEM = '9' WHERE arquivo_id = ? AND linha_num = ?", [aid, linha])
    visoes.preparar(con_param, forcar=True)
    g = _gama(con_param)
    assert g.loc[g.mes == 1, "nivel_cruzamento"].tolist() == ["N2_ITEM_CFOP"]
    assert g.loc[g.mes == 1, "vl_pis"].iloc[0] == 100
    _fecha(con_param)


def test_item_so_na_efd_nao_some(con_param):
    aid, linha, pai, _ = _gama_entradas(con_param)[0]
    con_param.execute(f"""INSERT INTO raw_contrib_c170 SELECT * REPLACE (linha_num + 500000 AS linha_num, '2' AS NUM_ITEM,
                              'INS99' AS COD_ITEM, 7 AS VL_PIS, 32.2 AS VL_COFINS)
                          FROM raw_contrib_c170 WHERE arquivo_id = {aid} AND linha_num = {linha}""")
    visoes.preparar(con_param, forcar=True)
    g = _gama(con_param)
    so = g[g.nivel_cruzamento == "EC_SEM_PAR"]
    assert len(so) == 1 and so["vl_pis"].iloc[0] == 7 and so["valor"].iloc[0] == 0  # valor zero: nao duplica a nota
    assert len(conciliacoes.CHECAGENS["Q19"][1](con_param)) == 1
    _fecha(con_param)


def test_efd_sem_sped_fiscal_entra_como_exclusivo(con_param):
    _gama_entradas(con_param)
    con_param.execute("""UPDATE arquivos SET ativo = FALSE WHERE tipo = 'ICMS_IPI' AND cnpj = '33333333000214'
                         AND month(dt_ini) = 1""")
    visoes.preparar(con_param, forcar=True)
    g = _gama(con_param)
    jan = g[g.mes == 1]
    assert jan["nivel_cruzamento"].tolist() == ["EC_EXCLUSIVO"]
    assert jan["valor"].iloc[0] == pytest.approx(30000.0) and jan["vl_pis"].iloc[0] == 100


def test_excecao_2_itens_vem_da_efd_contribuicoes(con_param):
    _gama_entradas(con_param)
    doc = con_param.execute("""SELECT d.arquivo_id, d.linha_num FROM raw_icms_c100 d JOIN arquivos a USING (arquivo_id)
                               WHERE a.cnpj = '33333333000214' AND month(a.dt_ini) = 1 AND d.IND_OPER = '0'""").fetchall()[0]
    con_param.execute("DELETE FROM raw_icms_c170 WHERE arquivo_id = ? AND pai_linha = ?", list(doc))
    visoes.preparar(con_param, forcar=True)
    g = _gama(con_param)
    jan = g[g.mes == 1]
    assert jan["reg_origem"].tolist() == ["C170 (EFD Contribuições)"]
    assert jan["cod_item"].iloc[0] == "INS01" and jan["vl_pis"].iloc[0] == 100
    assert jan["valor"].iloc[0] == pytest.approx(30000.0)  # rateado ao C190 do mesmo CFOP
    _fecha(con_param)


def test_nota_sem_chave_vincula_por_numero(con_param):
    _gama_entradas(con_param)
    con_param.execute("""UPDATE raw_icms_c100 SET CHV_NFE = NULL WHERE IND_OPER = '0' AND arquivo_id IN
                         (SELECT arquivo_id FROM arquivos WHERE cnpj = '33333333000214')""")
    visoes.preparar(con_param, forcar=True)
    vias = con_param.execute("SELECT via, count(*) FROM v_doc_par GROUP BY 1 ORDER BY 1").fetchall()
    assert ("NUMERO", 3) in vias
    assert set(_gama(con_param)["nivel_cruzamento"]) == {"N1_ITEM"}
    _fecha(con_param)


def test_diagnostico_por_nivel(con_param):
    d = cz.diagnostico_niveis(con_param)
    assert {"N1_ITEM", "N3_CONSOLIDADO_C190"} <= set(d["nivel_cruzamento"])
    assert d.groupby(["cnpj_estab", "mes"])["pct_linhas"].sum().round(6).eq(100).all()
