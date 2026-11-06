"""Conciliacoes Q3 a Q11: caso positivo (fecha) e negativo (divergencia)."""
from __future__ import annotations

from zfm import conciliacoes as c
from zfm import params, visoes
from zfm.parsers import carregar_arquivo


def _alterar(pasta, nome, de, para):
    p = pasta / nome
    txt = p.read_bytes().decode("latin-1")
    assert de in txt
    p.write_bytes(txt.replace(de, para, 1).encode("latin-1"))


def test_q3_a_q6_e_q9_q10_q11_fecham(con_param):
    for k in ("Q3", "Q4", "Q5", "Q6", "Q9", "Q10", "Q11"):
        assert c.CHECAGENS[k][1](con_param).empty, k


def test_q7_q8_apontam_so_o_esperado(con_param):
    # matriz da Gama esta em SP: receita dela entra no bloco M mas nao ha EFD ICMS/IPI do AM
    q7 = c.q7_icms_x_contrib(con_param)
    assert q7.empty
    q8 = c.q8_receita_contrib_x_icms(con_param)
    assert set(q8["raiz"]) == {"33333333"}
    assert q8["observacao"].str.contains("fora do AM").all()


def test_divergencias_detectadas(con, pasta_efd):
    nome = "EFD_ICMS_IPI_11111111000191_202601.txt"
    # Q3/Q4: altera o valor do C170 de uma entrada e o ICMS de um C190
    _alterar(pasta_efd, nome, "|C170|1|INS01||10,00000|UN|100000,00|", "|C170|1|INS01||10,00000|UN|100500,00|")
    _alterar(pasta_efd, nome, "|C190|000|2101|7,00|100000,00|100000,00|7000,00|",
             "|C190|000|2101|7,00|100000,00|100000,00|7100,00|")
    # Q9/Q10: aliquota de COFINS fora do padrao na Contribuicoes da Alfa
    _alterar(pasta_efd, "EFD_CONTRIB_11111111000191_202601.txt", "|C185|02|6101|400000,00|0,00|400000,00|3,0000|",
             "|C185|02|6101|400000,00|0,00|400000,00|2,0000|")
    for p in sorted(pasta_efd.glob("*.txt")):
        carregar_arquivo(con, p)
    visoes.preparar(con)
    params.preencher_a_partir_das_efds(con)
    visoes.preparar(con)
    assert len(c.q3_c170_x_c100(con)) == 1
    assert len(c.q4_c190_x_c100(con)) == 1
    q5 = c.q5_docs_x_e110(con)
    assert len(q5) == 1 and abs(float(q5["dif_creditos"].iloc[0]) - 100) < 0.01
    assert len(c.q9_aliquotas_pis_cofins(con)) == 1
    # Q11: codigo novo sem classificacao
    cod = params.carregar("param_codigos_ajuste_icms")
    params.salvar("param_codigos_ajuste_icms", cod[cod.codigo != "FTI9"])
    visoes.preparar(con)
    q11 = c.q11_codigos_nao_classificados(con)
    assert list(q11["codigo"]) == ["FTI9"]


def test_q10_cst_ipi_diferente_de_isento(con_param):
    # Gama (detalhada) traz CST de IPI por item; troca a premissa para que 52 nao seja isento
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "cst_ipi_isento", "valor"] = "50"
    params.salvar("param_premissas", pr)
    q10 = c.q10_cst_ipi_incentivado(con_param)
    assert set(q10["raiz"]) == {"33333333"} and len(q10) == 3
