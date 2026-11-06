"""Visoes normalizadas: escrituracao detalhada e consolidada, rateio, origem das entradas."""
from __future__ import annotations


def test_saidas_detalhada_e_consolidada(con_param):
    r = dict(con_param.execute(
        "SELECT raiz, string_agg(DISTINCT reg_origem, ',') FROM v_saidas_item GROUP BY 1").fetchall())
    assert r["11111111"] == "C181/C185"   # Alfa: consolidada
    assert r["33333333"] == "C170"        # Gama: detalhada


def test_pis_e_cofins_casados_no_c181_c185(con_param):
    n = con_param.execute("""SELECT count(*) FROM v_saidas_item
                             WHERE reg_origem = 'C181/C185' AND (aliq_pis IS NULL OR aliq_cofins IS NULL)""").fetchall()
    assert n[0][0] == 0


def test_rateio_preserva_receita(con_param):
    a, b = con_param.execute("""
        SELECT (SELECT sum(receita) FROM v_saidas_item), (SELECT sum(receita_r) FROM v_saidas_dest)""").fetchall()[0]
    assert abs(float(a) - b) < 0.01


def test_destino_exato_na_detalhada(con_param):
    t = con_param.execute("""SELECT DISTINCT tipo_operacao FROM v_saidas_dest
                             WHERE cnpj_estab = '33333333000214'""").fetchall()
    assert t == [("interestadual",)]


def test_destino_rateado_na_consolidada(con_param):
    # Alfa 0001 vende 5101 para Manaus (ZFM) e para a Beta (grupo): rateio pelo C190
    r = con_param.execute("""
        SELECT eh_grupo, round(sum(fator_rateio), 6) FROM v_saidas_dest
        WHERE cnpj_estab = '11111111000191' AND mes = 1 AND cfop = '5101' AND cod_item = 'PROD01'
        GROUP BY 1 ORDER BY 1""").fetchall()
    assert len(r) == 2 and abs(sum(x[1] for x in r) - 1) < 1e-6
    tipos = {x[0] for x in con_param.execute("""SELECT DISTINCT tipo_operacao FROM v_saidas_dest
            WHERE cnpj_estab = '11111111000191' AND cfop = '5101'""").fetchall()}
    assert tipos == {"zfm_interna"}


def test_origem_das_entradas(con_param):
    r = dict(con_param.execute("""SELECT regiao_origem, sum(valor) FROM v_entradas_item
                                  WHERE raiz = '11111111' AND mes = 1 GROUP BY 1""").fetchall())
    assert float(r["Sul/Sudeste exceto ES"]) == 140000.0
    assert float(r["Norte, Nordeste, Centro-Oeste e ES"]) == 20000.0
    assert float(r["Importação"]) == 50000.0
    z = con_param.execute("""SELECT origem, eh_grupo FROM v_entradas_item
                             WHERE raiz = '22222222' AND cfop = '1101' LIMIT 1""").fetchall()
    assert z == [("zfm", True)]


def test_apuracao_icms_classificada(con_param):
    r = con_param.execute("""SELECT credito_estimulo, fundos FROM v_apur_icms
                             WHERE cnpj_estab = '11111111000191' AND mes = 1""").fetchall()[0]
    assert float(r[0]) == 38500.0 and float(r[1]) == 385.0


def test_estab_fora_do_am_marcado(con_param):
    r = con_param.execute("""SELECT DISTINCT estab_no_am FROM v_saidas_item
                             WHERE cnpj_estab = '33333333000133'""").fetchall()
    assert r == [(False,)]
