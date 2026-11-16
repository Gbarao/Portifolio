"""Leitura correta das EFDs: conversao invalida avisada, CNPJ alfanumerico, C181 x C185 sem par."""
from __future__ import annotations

from tests.fixtures.gerador import gerar_icms, montar_cenario
from zfm import visoes
from zfm.filtros import Filtro
from zfm.parsers import carregar_arquivo


def test_valor_invalido_gera_aviso(con, tmp_path):
    emp = montar_cenario(meses=(1,))
    txt = gerar_icms(emp[0].estabs[0], 1)
    # valor com separador de milhar (formato invalido no SPED) e data invalida
    txt = txt.replace("|C170|1|INS01||10,00000|UN|100000,00|", "|C170|1|INS01||10,00000|UN|100.000,00|", 1)
    txt = txt.replace("|03012026|03012026|", "|32012026|03012026|", 1)
    p = tmp_path / "invalido.txt"
    p.write_bytes(txt.encode("latin-1"))
    r = carregar_arquivo(con, p)
    assert r.situacao == "carregado"
    assert any("VL_ITEM" in a and "100.000,00" in a for a in r.avisos)
    assert any("DT_DOC" in a for a in r.avisos)


def test_cnpj_alfanumerico(con, tmp_path):
    emp = montar_cenario(meses=(1,))
    txt = gerar_icms(emp[0].estabs[0], 1).replace("66666666000166", "12ABC34501DE35")
    p = tmp_path / "alfa.txt"
    p.write_bytes(txt.encode("latin-1"))
    assert carregar_arquivo(con, p).situacao == "carregado"
    visoes.preparar(con)
    r = con.execute("SELECT DISTINCT cnpj_part FROM v_docs WHERE cnpj_part LIKE '12ABC%'").fetchall()
    assert r == [("12ABC34501DE35",)]
    assert "'12ABC34501DE35'" in Filtro(estabs=("12ABC34501DE35",)).sql()


def test_filtro_nao_aceita_injecao():
    sql = Filtro(raizes=("1111'; DROP TABLE x; --",)).sql()
    assert "DROP" in sql and "'" not in sql.split("IN (")[1].split(")")[0].strip("'")


def test_c185_sem_par_nao_duplica_receita(con, pasta_efd):
    """COFINS informada em duas linhas e PIS em uma (mesmo C180): a receita conta uma vez."""
    p = pasta_efd / "EFD_CONTRIB_11111111000191_202601.txt"
    txt = p.read_bytes().decode("latin-1")
    velho = "|C185|02|6101|400000,00|0,00|400000,00|3,0000|||12000,00||"
    assert velho in txt
    txt = txt.replace(velho, "|C185|02|6101|300000,00|0,00|300000,00|3,0000|||9000,00||\r\n"
                             "|C185|02|6101|100000,00|0,00|100000,00|3,0000|||3000,00||")
    p.write_bytes(txt.encode("latin-1"))
    for q in sorted(pasta_efd.glob("*.txt")):
        carregar_arquivo(con, q)
    visoes.preparar(con)
    rec, rec_cof, cof = con.execute("""
        SELECT sum(receita), sum(receita_cofins), sum(vl_cofins) FROM v_saidas_item
        WHERE cnpj_estab = '11111111000191' AND mes = 1""").fetchall()[0]
    c180 = con.execute("""SELECT sum(VL_TOT_ITEM) FROM raw_contrib_c180 h JOIN arquivos a USING (arquivo_id)
                          WHERE h.cnpj_estab = '11111111000191' AND month(a.dt_ini) = 1""").fetchall()[0][0]
    assert rec == c180 and rec_cof == c180
    assert float(cof) == 12000.0
