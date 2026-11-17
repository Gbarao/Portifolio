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
