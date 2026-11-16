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


def test_conciliacoes_fecham_nas_fixtures(con_param):
    for k in ("Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10", "Q13"):
        assert c.CHECAGENS[k][1](con_param).empty, k


def test_q11_aponta_so_codigo_sem_regra(con_param):
    # AM009001 (ajuste de debito sem palavra-chave) fica 'nao_classificado' e gera alerta
    q11 = c.q11_codigos_nao_classificados(con_param)
    assert list(q11["codigo"]) == ["AM009001"]
    # E116 com COD_OR 000 (ICMS proprio a recolher) nao e alerta
    assert "1234" not in set(q11["codigo"])


def test_q12_mostra_fundo_fora_da_apuracao(con_param):
    # FTI informado no E116 alem do ICMS a recolher (Alfa 0001 e Gama filial, todos os meses)
    q12 = c.q12_e116_x_e110(con_param)
    assert set(q12["cnpj_estab"]) == {"11111111000191", "33333333000214"}
    jan = q12[(q12.cnpj_estab == "11111111000191") & (q12.mes == 1)]
    assert float(jan["diferenca"].iloc[0]) == 385.0


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
    assert set(q11["codigo"]) == {"FTI9", "AM009001"}


def test_q10_cst_ipi_diferente_de_isento(con_param):
    # Gama (detalhada) traz CST de IPI por item; troca a premissa para que 52 nao seja isento
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "cst_ipi_isento", "valor"] = "50"
    params.salvar("param_premissas", pr)
    q10 = c.q10_cst_ipi_incentivado(con_param)
    assert set(q10["raiz"]) == {"33333333"} and len(q10) == 3


def test_r1_r5_detectam_base_incompleta(con, pasta_efd):
    """ICMS de um C190 de saida alterado sem mexer no E110: R1 (Q5) e R5 apontam a diferenca."""
    from zfm import as_is
    _alterar(pasta_efd, "EFD_ICMS_IPI_22222222000122_202601.txt",
             "|C190|000|6101|12,00|100000,00|100000,00|12000,00|",
             "|C190|000|6101|12,00|100000,00|100000,00|12500,00|")
    for p in sorted(pasta_efd.glob("*.txt")):
        carregar_arquivo(con, p)
    visoes.preparar(con)
    assert len(c.q5_docs_x_e110(con)) == 1
    r5 = as_is.reconciliacao_r5(con)
    # Beta tem saldo credor de ICMS: +500 de debito so reduz o saldo, a carga continua zero
    assert r5["fecha"].all()
    # Na Alfa (ICMS a recolher) a mesma alteracao muda a carga recalculada
    _alterar(pasta_efd, "EFD_ICMS_IPI_11111111000272_202601.txt",
             "|C190|000|6101|12,00|150000,00|150000,00|18000,00|",
             "|C190|000|6101|12,00|150000,00|150000,00|18300,00|")
    from zfm import db
    db.apagar_dados(con)
    for p in sorted(pasta_efd.glob("*.txt")):
        carregar_arquivo(con, p)
    visoes.preparar(con)
    r5 = as_is.reconciliacao_r5(con)
    nao = r5[~r5.fecha]
    assert list(nao["cnpj_estab"]) == ["11111111000272"] and float(nao["diferenca"].iloc[0]) == -300.0
