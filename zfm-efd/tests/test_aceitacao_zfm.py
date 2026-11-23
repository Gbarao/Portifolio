"""Testes de aceitacao dos seis macrocenarios (LC 214/2025, arts. 440-455).

As aliquotas de IBS/CBS/IPI sao premissas de simulacao informadas no teste; os percentuais legais e as
vigencias vem de param_regras_legais (modelos do programa)."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal as D

import pytest

from zfm import params, regras_zfm as rz, visoes

DATA_2029 = dt.date(2029, 6, 1)
OK = True


def _req_ok(*nomes):
    return {n: True for n in nomes}


# 1. Art. 443: importacao elegivel gera suspensao e posterior isencao
def test_01_art443_suspensao_e_isencao():
    r = rz.art443_importacao(D("1000"), D("1000"), D("18"), D("9"), DATA_2029,
                             _req_ok("indústria incentivada habilitada", "projeto aprovado", "utilização na ZFM",
                                     "bem não excluído (art. 441)", "não é uso e consumo pessoal"))
    assert r.status == rz.ELEGIVEL
    assert r.valores["ibs_suspenso"] == D("180.00") and r.valores["cbs_suspensa"] == D("90.00")
    assert r.valores["desembolso_inicial"] == 0
    convertido, motivo = rz.art443_conversao(dt.date(2029, 1, 10), dt.date(2033, 1, 10))
    assert convertido and "48" in motivo
    assert rz.art443_conversao(dt.date(2029, 1, 10), dt.date(2029, 3, 1), consumido=True)[0]
    assert not rz.art443_conversao(dt.date(2029, 1, 10), dt.date(2030, 1, 10))[0]


# 2. Art. 443: saida antes da conversao -> principal, acrescimos e credito so sobre o principal
def test_02_art443_saida_antes_da_conversao():
    pr = params.carregar("param_premissas")
    pr.loc[pr.chave == "taxa_juros_acrescimos_mes", "valor"] = "1"
    pr.loc[pr.chave == "multa_acrescimos_pct", "valor"] = "20"
    params.salvar("param_premissas", pr)
    r = rz.art443_saida_antes(D("180"), D("90"), dt.date(2029, 1, 15), dt.date(2029, 11, 15))
    assert r.valores["principal"] == D("270.00")
    assert r.valores["juros"] == D("27.00") and r.valores["multa"] == D("54.00")   # 10 meses × 1% ; 20%
    assert r.valores["credito_ordinario_apos_pagamento"] == D("270.00")           # sem acrescimos


def test_02b_acrescimos_sem_parametro_ficam_pendentes():
    r = rz.art443_saida_antes(D("180"), D("90"), dt.date(2029, 1, 15), dt.date(2029, 11, 15))
    assert r.valores["juros"] == 0 and any("pendentes" in f for f in r.formulas)


# 3. Art. 444: base 1.000, IBS 18% -> nominal 180, CP 90, recolhe 90
def test_03_art444():
    r = rz.art444(D("1000"), D("1000"), D("18"), D("9"), DATA_2029, True,
                  _req_ok("habilitado", "revenda presencial", "ingresso comprovado", "bem não excluído (art. 441)"))
    assert r.valores["ibs_nominal"] == D("180.00")
    assert r.valores["credito_presumido_ibs"] == D("90.00")
    assert r.valores["ibs_recolher_importacao"] == D("90.00")
    assert r.valores["credito_ordinario_ibs"] == D("180.00")


# 4 e 5. Art. 447: origem SP -> 75 ; origem BA -> 135
@pytest.mark.parametrize("uf,esperado", [("SP", D("75.00")), ("BA", D("135.00")), ("ES", D("135.00"))])
def test_04_05_art447(uf, esperado):
    r = rz.art445_447(D("1000"), D("18"), D("9"), uf, DATA_2029, industria_incentivada=False, utilizacao_zfm=True,
                      regime="regular", requisitos=_req_ok("habilitado", "ingresso na ZFM comprovado",
                                                            "origem nacional", "bem não excluído (art. 441)"))
    assert r.valores["credito_presumido_ibs_art447"] == esperado
    assert r.valores["ibs_saida_fornecedor"] == 0 and r.valores["cbs_saida_fornecedor"] == 0
    assert r.valores["ibs_entrada_art446"] == D("126.00")          # 1.000 × 18% × 70%


def test_art446_industria_incentivada_com_utilizacao_na_zfm_nao_paga_ibs_na_entrada():
    r = rz.art445_447(D("1000"), D("18"), D("9"), "SP", DATA_2029, True, True, "regular",
                      _req_ok("habilitado", "ingresso na ZFM comprovado"))
    assert r.valores["ibs_entrada_art446"] == 0 and r.valores["credito_presumido_ibs_art447"] == D("75.00")


def test_art447_encomenda_so_sobre_valor_agregado_e_vigencia():
    r = rz.art445_447(D("1000"), D("18"), D("9"), "SP", DATA_2029, True, True, "regular",
                      _req_ok("habilitado", "ingresso na ZFM comprovado"), valor_agregado_encomenda=D("200"))
    assert r.valores["credito_presumido_ibs_art447"] == D("15.00")
    antes = rz.art445_447(D("1000"), D("18"), D("9"), "SP", dt.date(2028, 6, 1), True, True, "regular",
                          _req_ok("habilitado", "ingresso na ZFM comprovado"))
    assert antes.valores["credito_presumido_ibs_art447"] == 0      # art. 447 so a partir de 2029


# 6. Art. 449: base 1.000 -> 75
def test_06_art449():
    r = rz.art448_449(D("1000"), DATA_2029, _req_ok("fornecedor indústria incentivada", "adquirente indústria incentivada",
                                                     "bem intermediário", "bem incorporado/consumido na produção de bem final"))
    assert r.valores["credito_presumido_ibs_art449"] == D("75.00")
    assert r.valores["ibs_operacao"] == 0 and r.valores["credito_presumido_art450"] == 0  # trava do art. 450


# 7. Art. 450 IBS: saldo devedor elegivel de 1.000 em bem final -> 550 (sobre o saldo, nao sobre a receita)
def test_07_art450_ibs_saldo_devedor():
    r = rz.art450_ibs({"55": D("1500")}, D("0"), D("500"), DATA_2029)
    assert r.valores["saldo_devedor_55"] == D("1000.00")
    assert r.valores["credito_presumido_ibs_total"] == D("550.00")
    misto = rz.art450_ibs({"55": D("1000"), "90_25": D("1000")}, D("0"), D("0"), DATA_2029)
    assert misto.valores["credito_presumido_ibs_total"] == D("1452.50")   # 550 + 902,50, sem média ponderada


# 8. Art. 450 CBS: base 1.000 -> 60 (produto do art. 454) e 20 (demais)
def test_08_art450_cbs():
    seis = rz.art450_cbs(D("1000"), DATA_2029, True, True, False, {})
    dois = rz.art450_cbs(D("1000"), DATA_2029, False, True, False, {})
    assert seis.valores["credito_presumido_cbs"] == D("60.00") and dois.valores["credito_presumido_cbs"] == D("20.00")
    assert rz.art450_cbs(D("1000"), DATA_2029, True, False, False, {}).valores["credito_presumido_cbs"] == 0
    assert rz.art450_cbs(D("1000"), DATA_2029, True, True, True, {}).valores["credito_presumido_cbs"] == 0  # art. 448


# 9. Art. 451: CBS zero e IBS pela aliquota parametrizada
def test_09_art451():
    r = rz.art451(D("1000"), D("18"), D("9"), _req_ok("fornecedor PJ na ZFM", "adquirente na ZFM", "origem nacional"))
    assert r.valores["cbs_operacao"] == 0 and r.valores["ibs_operacao"] == D("180.00")
    assert r.valores["beneficio_cbs"] == D("90.00")
    srv = rz.art451(D("1000"), D("18"), D("9"), {"local físico da prestação na ZFM comprovado": None}, servico=True)
    assert srv.status == rz.POTENCIAL


# 10. Art. 454: IPI futuro zero a partir da vigencia
def test_10_art454():
    r = rz.art454(D("5"), True, None, False, False, D("1000"), 2027)
    assert r.valores["ipi_historico"] == D("50.00") and r.valores["ipi_futuro"] == 0
    assert rz.art454(D("15"), True, None, False, False, D("1000"), 2027).valores["ipi_futuro"] == D("150.00")
    assert rz.art454(D("5"), True, None, False, False, D("1000"), 2026).valores["ipi_futuro"] == D("50.00")


# Precos: liquido constante, bruto constante, repasse parcial
def test_motor_de_precos():
    liq = rz.precos("liquido_constante", D("1000"), D("18"), D("9"))
    assert liq["preco_bruto"] == D("1270.00")
    bru = rz.precos("bruto_constante", D("1270"), D("18"), D("9"))
    assert bru["preco_liquido"] == D("1000.00")
    meio = rz.precos("repasse_parcial", D("1000"), D("18"), D("9"), repasse_pct=D("50"))
    assert meio["preco_bruto"] == pytest.approx(D("1135.00"), abs=D("0.02"))


# ---------------------------------------------------------------------------
# Testes sobre as EFDs sinteticas (classificacao e requisitos)
# ---------------------------------------------------------------------------
def _prod(con, cod, **campos):
    p = params.carregar("param_produtos")
    for k, v in campos.items():
        p.loc[p.cod_item == cod, k] = v
    params.salvar("param_produtos", p)
    visoes.preparar(con)


# 11. Art. 441: bebida alcoolica nao recebe o incentivo
def test_11_art441_bebida_alcoolica(con_param):
    vendas = con_param.execute("SELECT DISTINCT cod_item FROM v_cenarios WHERE cenario LIKE 'C4%'").fetchall()
    cod = vendas[0][0]
    _prod(con_param, cod, excluido_art441="sim", motivo_exclusao="bebida alcoólica")
    linhas = con_param.execute(f"""SELECT DISTINCT cenario, status_elegibilidade, motivo FROM v_cenarios
                                   WHERE cod_item = '{cod}' AND cenario_candidato LIKE 'C4%'""").fetchall()
    assert linhas and all(c == "GER_S" and s == "Não elegível" and "bebida alcoólica" in m for c, s, m in linhas)


# 12. Internamento: sem comprovacao -> risco (potencialmente elegivel) e recuperacao calculada
def test_12_internamento(con_param):
    st = con_param.execute("""SELECT DISTINCT status_elegibilidade, req_ingresso FROM v_cenarios
                              WHERE cenario_candidato LIKE 'C2%'""").fetchall()
    assert st and all(s != rz.ELEGIVEL and r == "pendente" for s, r in st)
    r = rz.art445_447(D("1000"), D("18"), D("9"), "SP", DATA_2029, True, True, "regular",
                      {"habilitado": True, "ingresso na ZFM comprovado": None})
    assert r.status == rz.POTENCIAL and r.valores["valor_sujeito_a_estorno"] == D("75.00")
    # comprovacao cadastrada muda o requisito
    chv = con_param.execute("SELECT chv_nfe FROM v_cenarios WHERE cenario_candidato LIKE 'C2%' LIMIT 1").fetchall()[0][0]
    params.salvar("param_internamento", params.normalizar("param_internamento", __import__("pandas").DataFrame(
        [{"chv_nfe": chv, "status": "confirmado", "data_ingresso": "2026-01-20"}])))
    visoes.preparar(con_param)
    assert con_param.execute(f"SELECT DISTINCT req_ingresso FROM v_cenarios WHERE chv_nfe = '{chv}'"
                             ).fetchall() == [("ok",)]


# 13. Duplicidade: a mesma NF-e nas duas EFDs entra uma unica vez na base
def test_13_duplicidade(con_param):
    dup = con_param.execute("""SELECT chv_nfe, sentido, count(DISTINCT reg_origem) FROM v_cenarios
                               WHERE chv_nfe IS NOT NULL AND cnpj_estab = '33333333000214' GROUP BY ALL
                               HAVING count(DISTINCT reg_origem) > 1""").fetchall()
    assert dup == []
    n_par = con_param.execute("SELECT count(*) FROM v_doc_par").fetchall()[0][0]
    assert n_par == 6  # documentos da Gama presentes nas duas EFDs, vinculados 1:1


# 14. Dados insuficientes: ausencia de projeto SUFRAMA nao e substituida por suposicao
def test_14_sem_projeto_suframa(con_param):
    r = con_param.execute("""SELECT DISTINCT req_projeto, status_elegibilidade FROM v_cenarios
                             WHERE cenario_candidato LIKE 'C4%'""").fetchall()
    assert r and all(p == "pendente" and s != rz.ELEGIVEL for p, s in r)
    # projeto cadastrado sem o produto -> falha (produto fora do projeto) -> regra geral
    est = con_param.execute("SELECT DISTINCT cnpj_estab FROM v_cenarios WHERE cenario_candidato LIKE 'C4%' LIMIT 1"
                            ).fetchall()[0][0]
    import pandas as pd
    params.salvar("param_projetos_suframa", pd.DataFrame([{"cnpj": est, "projeto": "P1", "cod_item": "OUTRO",
                                                            "status": "aprovado"}]))
    visoes.preparar(con_param)
    r2 = con_param.execute(f"""SELECT DISTINCT cenario, status_elegibilidade FROM v_cenarios
                               WHERE cenario_candidato LIKE 'C4%' AND cnpj_estab = '{est}'""").fetchall()
    assert all(c == "GER_S" and s == "Não elegível" for c, s in r2)


def test_elegivel_quando_todos_os_requisitos_comprovados(con_param):
    import pandas as pd
    ez = params.carregar("param_empresas_zfm")
    ez["revisado"] = True
    ez["status_habilitacao"] = "ativa"
    params.salvar("param_empresas_zfm", ez)
    est = con_param.execute("SELECT DISTINCT cnpj_estab, cod_item FROM v_cenarios WHERE cenario_candidato = 'C4a' LIMIT 1"
                            ).fetchall()[0]
    params.salvar("param_projetos_suframa", pd.DataFrame([{"cnpj": est[0], "projeto": "P1", "cod_item": est[1],
                                                            "status": "aprovado"}]))
    _prod(con_param, est[1], excluido_art441="nao")
    st = con_param.execute(f"""SELECT DISTINCT status_elegibilidade FROM v_cenarios
                               WHERE cenario = 'C4a' AND cnpj_estab = '{est[0]}' AND cod_item = '{est[1]}'""").fetchall()
    assert st == [(rz.ELEGIVEL,)]
