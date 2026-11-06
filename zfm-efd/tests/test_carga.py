"""Carga: retificadora, duplicidade, transacao."""
from __future__ import annotations

from tests.fixtures.gerador import gerar_conjunto
from zfm.parsers import carregar_arquivo, listar_txt


def test_carrega_conjunto_completo(con_carregado):
    n = con_carregado.execute("SELECT tipo, count(*) FROM arquivos GROUP BY 1 ORDER BY 1").fetchall()
    # 3 empresas x 3 meses na Contribuicoes; 4 estabelecimentos do AM x 3 meses na ICMS/IPI
    assert n == [("CONTRIB", 9), ("ICMS_IPI", 12)]


def test_arquivo_duplicado_nao_e_carregado_de_novo(con_carregado, pasta_efd):
    p = sorted(pasta_efd.glob("*.txt"))[0]
    antes = con_carregado.execute("SELECT count(*) FROM raw_icms_c100").fetchall()[0][0]
    r = carregar_arquivo(con_carregado, p)
    assert r.situacao == "duplicado"
    assert con_carregado.execute("SELECT count(*) FROM arquivos").fetchall()[0][0] == 21
    assert con_carregado.execute("SELECT count(*) FROM raw_icms_c100").fetchall()[0][0] == antes


def test_retificadora_substitui_original(con, tmp_path):
    pasta = tmp_path / "r"
    gerar_conjunto(pasta, meses=(1,), retificadora=True)
    for p in listar_txt(pasta):
        carregar_arquivo(con, p)
    r = con.execute(
        """SELECT nome_arquivo, ativo FROM arquivos
           WHERE cnpj = '11111111000191' AND tipo = 'ICMS_IPI' ORDER BY arquivo_id""").fetchall()
    assert dict(r) == {"EFD_ICMS_IPI_11111111000191_202601.txt": False,
                       "EFD_ICMS_IPI_11111111000191_202601_RETIFICADORA.txt": True}


def test_original_carregada_depois_da_retificadora_fica_inativa(con, tmp_path):
    pasta = tmp_path / "r"
    gerar_conjunto(pasta, meses=(1,), retificadora=True)
    ret = pasta / "EFD_ICMS_IPI_11111111000191_202601_RETIFICADORA.txt"
    orig = pasta / "EFD_ICMS_IPI_11111111000191_202601.txt"
    carregar_arquivo(con, ret)
    r = carregar_arquivo(con, orig)
    assert not r.ativo and "retificadora" in r.mensagem
    ativos = con.execute("SELECT nome_arquivo FROM arquivos WHERE ativo").fetchall()
    assert ativos == [(ret.name,)]


def test_pasta_inexistente():
    import pytest
    from zfm.parsers import ErroEFD
    with pytest.raises(ErroEFD):
        listar_txt("C:/pasta/que/nao/existe")


def test_apagar_dados(con_carregado):
    from zfm import db
    db.apagar_dados(con_carregado)
    assert con_carregado.execute("SELECT count(*) FROM arquivos").fetchall()[0][0] == 0
    assert con_carregado.execute("SELECT count(*) FROM raw_icms_c100").fetchall()[0][0] == 0
