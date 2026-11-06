"""Leitura: encoding, decimais, datas, hierarquia, registro apos o 9999."""
from __future__ import annotations

from decimal import Decimal

from tests.fixtures.gerador import gerar_conjunto, gerar_icms, montar_cenario
from zfm.parsers import carregar_arquivo
from zfm.parsers.base import detectar_encoding, identificar, separar_campos


def test_separar_campos():
    assert separar_campos("|C100|0|1||X|\r\n") == ["C100", "0", "1", "", "X"]
    assert separar_campos("   \r\n") is None


def test_encoding_latin1_e_utf8(tmp_path):
    a = tmp_path / "latin.txt"
    a.write_bytes("|0000|Amazônia|\r\n".encode("latin-1"))
    u = tmp_path / "utf.txt"
    u.write_bytes("|0000|Amazônia|\r\n".encode("utf-8"))
    s = tmp_path / "ascii.txt"
    s.write_bytes(b"|0000|ABC|\r\n")
    assert detectar_encoding(a) == "latin-1"
    assert detectar_encoding(u) == "utf-8"
    assert detectar_encoding(s) == "latin-1"


def test_nome_com_acento_lido_corretamente(con_carregado):
    nomes = {r[0] for r in con_carregado.execute("SELECT NOME FROM raw_icms_0000").fetchall()}
    assert "Alfa Eletrônicos da Amazônia Ltda" in nomes


def test_arquivo_utf8_tambem_e_lido(con, tmp_path):
    emp = montar_cenario()
    txt = gerar_icms(emp[0].estabs[0], 1)
    p = tmp_path / "utf8.txt"
    p.write_bytes(txt.encode("utf-8"))
    r = carregar_arquivo(con, p)
    assert r.situacao == "carregado"
    nome = con.execute("SELECT NOME FROM raw_icms_0000").fetchall()[0][0]
    assert nome == "Alfa Eletrônicos da Amazônia Ltda"


def test_identificacao_tipo():
    i = identificar("0000|020|0|01012026|31012026|X|11111111000191||AM|1|1302603||1|A|0".split("|"))
    assert i.tipo == "ICMS_IPI" and not i.retificador
    c = identificar("0000|006|1|||01012026|31012026|X|11111111000191|AM|1302603||00|0".split("|"))
    assert c.tipo == "CONTRIB" and c.retificador


def test_decimais_e_datas(con_carregado):
    r = con_carregado.execute(
        """SELECT VL_ITEM, ALIQ_ICMS, VL_ICMS, QTD, typeof(VL_ITEM), typeof(ALIQ_PIS)
           FROM raw_icms_c170 WHERE COD_ITEM = 'INS01' AND CFOP = '2101'
           ORDER BY arquivo_id, linha_num LIMIT 1""").fetchall()[0]
    assert r[0] == Decimal("100000.00")
    assert r[1] == Decimal("7.0000")
    assert r[2] == Decimal("7000.00")
    assert r[3] == Decimal("10")
    assert r[4] == "DECIMAL(18,2)"
    assert r[5] == "DECIMAL(18,4)"
    d = con_carregado.execute(
        "SELECT DT_DOC, typeof(DT_DOC) FROM raw_icms_c100 ORDER BY arquivo_id, linha_num LIMIT 1"
    ).fetchall()[0]
    assert str(d[0]) == "2026-01-03" and d[1] == "DATE"


def test_hierarquia_pai_filho(con_carregado):
    # Todo C170 aponta para um C100 do mesmo arquivo, e o item bate com o documento
    orfaos = con_carregado.execute(
        """SELECT count(*) FROM raw_icms_c170 i
           LEFT JOIN raw_icms_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
           WHERE d.linha_num IS NULL""").fetchall()[0][0]
    assert orfaos == 0
    # C170 de importacao (INS02) pertence ao C100 do participante estrangeiro
    part = con_carregado.execute(
        """SELECT DISTINCT d.COD_PART FROM raw_icms_c170 i
           JOIN raw_icms_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
           WHERE i.COD_ITEM = 'INS02'""").fetchall()
    assert part == [("F_EXT",)]
    # E111 pertence ao E110
    n = con_carregado.execute(
        """SELECT count(*) FROM raw_icms_e111 a JOIN raw_icms_e110 b
           ON a.arquivo_id = b.arquivo_id AND a.pai_linha = b.linha_num""").fetchall()[0][0]
    assert n == con_carregado.execute("SELECT count(*) FROM raw_icms_e111").fetchall()[0][0] > 0


def test_estabelecimento_propagado_na_contribuicoes(con_carregado):
    # C181 recebe o CNPJ do C010 anterior; M210 recebe o CNPJ da matriz
    r = con_carregado.execute(
        """SELECT DISTINCT cnpj_estab FROM raw_contrib_c181 c JOIN arquivos a USING (arquivo_id)
           WHERE a.raiz = '11111111' ORDER BY 1""").fetchall()
    assert r == [("11111111000191",), ("11111111000272",)]
    m = con_carregado.execute(
        """SELECT DISTINCT cnpj_estab FROM raw_contrib_m210 c JOIN arquivos a USING (arquivo_id)
           WHERE a.raiz = '33333333'""").fetchall()
    assert m == [("33333333000133",)]


def test_registro_apos_9999_ignorado(con, tmp_path):
    pasta = tmp_path / "ass"
    gerar_conjunto(pasta, meses=(1,), assinatura=True)
    p = sorted(pasta.glob("EFD_ICMS_IPI_11111111000191_*.txt"))[0]
    assert b"ASSINATURA" in p.read_bytes()
    r = carregar_arquivo(con, p)
    assert r.situacao == "carregado"
    # o "|0000|" falso depois do 9999 nao foi carregado
    assert con.execute("SELECT count(*) FROM raw_icms_0000").fetchall()[0][0] == 1
    assert r.avisos == []


def test_arquivo_que_nao_e_efd(con, tmp_path):
    p = tmp_path / "planilha.txt"
    p.write_text("nome;valor\nx;1\n")
    r = carregar_arquivo(con, p)
    assert r.situacao == "erro"
    assert "não parece ser uma EFD" in r.mensagem
    assert "Traceback" not in r.mensagem


def test_numero_de_campos_divergente_gera_aviso(con, tmp_path):
    emp = montar_cenario(meses=(1,))
    txt = gerar_icms(emp[0].estabs[0], 1)
    # acrescenta um campo extra em todos os C190 (simula layout novo)
    txt = "\r\n".join(l + "NOVO|" if l.startswith("|C190|") else l for l in txt.split("\r\n"))
    p = tmp_path / "novo.txt"
    p.write_bytes(txt.encode("latin-1"))
    r = carregar_arquivo(con, p)
    assert r.situacao == "carregado"
    assert any("C190" in a and "campos" in a for a in r.avisos)
    # campos conhecidos continuam corretos
    v = con.execute("SELECT sum(VL_ICMS) FROM raw_icms_c190").fetchall()[0][0]
    assert v > 0


def test_layout_anterior_reconhecido_pelo_numero_de_campos(con, tmp_path):
    emp = montar_cenario(meses=(1,))
    txt = gerar_icms(emp[0].estabs[0], 1)
    linhas = []
    for l in txt.split("\r\n"):
        if l.startswith("|0200|"):
            l = "|".join(l.split("|")[:-2]) + "|"  # remove CEST (layout anterior)
        linhas.append(l)
    p = tmp_path / "antigo.txt"
    p.write_bytes("\r\n".join(linhas).encode("latin-1"))
    r = carregar_arquivo(con, p)
    assert r.avisos == []
    v = con.execute("SELECT DISTINCT layout_versao FROM raw_icms_0200").fetchall()
    assert v == [("anterior_sem_CEST",)]
