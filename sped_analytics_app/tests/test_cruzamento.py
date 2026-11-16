"""Testes adversariais do cruzamento SPED Fiscal x EFD-Contribuições.

Cada cenário altera os arquivos sintéticos para reproduzir uma situação em que os dois arquivos NÃO são
espelhos perfeitos, e verifica as três garantias do motor:
  1. o PIS/COFINS nunca é atribuído ao item errado;
  2. nenhum centavo da EFD some do totalizador;
  3. nenhum centavo é contado duas vezes.
"""
from decimal import Decimal

import pytest

from app.database import analytics, audit
from app.database.aggregates import FATO
from app.database.engine import SpedDatabase
from tests import sample_data as sd

A, B = sd.CNPJ_A, sd.CNPJ_B
EFD_TOTAL_SQL = """SELECT coalesce(sum(v), 0) FROM (
    SELECT sum(i.{col}) v FROM ec_item i
    UNION ALL SELECT sum(vl) FROM ec_doc_trib WHERE tributo = '{trib}'
    UNION ALL SELECT sum(vl) FROM ec_c191_195 WHERE tributo = '{trib}'
    UNION ALL SELECT sum(f.{col}) FROM ec_f f)"""


def lines_of(text: str) -> list[str]:
    return text.split("\r\n")


def join(lines: list[str]) -> bytes:
    return "\r\n".join(lines).encode("latin-1")


def build(tmp_path, files: dict[str, bytes], name: str = "db") -> SpedDatabase:
    src = tmp_path / f"src_{name}"
    src.mkdir()
    for fname, content in files.items():
        (src / fname).write_bytes(content)
    db = SpedDatabase(db_path=tmp_path / f"{name}.duckdb", parquet_dir=tmp_path / f"pq_{name}")
    s = db.import_paths([src], workers=1)
    assert s.count("ERRO") == 0, [r.mensagem for r in s.resultados if r.acao == "ERRO"]
    return db


def assert_fechamento(db: SpedDatabase) -> None:
    """Total de PIS e COFINS da EFD == total na fato, e a auditoria de fechamento não aponta nada."""
    for col, trib in (("vl_pis", "PIS"), ("vl_cofins", "COFINS")):
        efd = db.scalar(EFD_TOTAL_SQL.format(col=col, trib=trib))
        fato = db.scalar(f"SELECT coalesce(sum({col}), 0) FROM {FATO}")
        assert Decimal(efd).quantize(Decimal("0.01")) == Decimal(fato).quantize(Decimal("0.01")), (trib, efd, fato)
    assert audit.run_check(db, "fechamento_efd").height == 0


def fato_rows(db: SpedDatabase, where: str) -> list[dict]:
    return db.query(f"SELECT origem, cod_item, cfop, vl_item, vl_contabil, vl_pis, vl_cofins, "
                    f"nivel_cruzamento_efd AS nivel, status_efd, competencia FROM {FATO} WHERE {where} "
                    f"ORDER BY origem, cod_item").to_dicts()


def base_files(comp: str = "2024-01") -> dict[str, list[str]]:
    return {"SF_A.txt": lines_of(sd.sped_fiscal(A, "SP", comp)), "EFD.txt": lines_of(sd.efd_contrib(comp))}


def idx(lines: list[str], prefix: str, contains: str = "") -> int:
    return next(i for i, l in enumerate(lines) if l.startswith(prefix) and contains in l)


# ------------------------------------------------------------------------------------------------------------
def test_numeracao_invertida_nao_troca_credito(tmp_path):
    """EFD numera os itens em ordem diferente do SPED Fiscal: o crédito segue o COD_ITEM, não a posição."""
    f = base_files()
    e = f["EFD.txt"]
    i1, i2 = idx(e, "|C170|1|P1|"), idx(e, "|C170|2|P2|", "|500,00|")
    e[i1] = e[i1].replace("|C170|1|P1|", "|C170|2|P1|", 1)
    e[i2] = e[i2].replace("|C170|2|P2|", "|C170|1|P2|", 1)
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    rows = {r["cod_item"]: r for r in fato_rows(db, f"cnpj_filial = '{A}' AND origem = 'SF_C170'")}
    assert rows["P1"]["vl_pis"] == Decimal("16.50") and rows["P1"]["nivel"] == "N2_ITEM_CFOP"
    assert rows["P2"]["vl_pis"] == Decimal("8.25") and rows["P2"]["nivel"] == "N2_ITEM_CFOP"
    assert_fechamento(db)
    db.close()


def test_item_somente_na_efd_nao_some(tmp_path):
    """Item com crédito na EFD que não existe na mesma nota do SPED Fiscal vira linha 'Somente EFD'."""
    f = base_files()
    e = f["EFD.txt"]
    e.insert(idx(e, "|C170|2|P2|", "|500,00|") + 1,
             "|C170|3|P9||1,00000|UN|100,00|0,00|0|000|1102||0,00|0,00|0,00|0,00|0,00|0,00|0|49||0,00|0,00|0,00|50|"
             "100,00|1,6500|||1,65|50|100,00|7,6000|||7,60|1.1.01|")
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    sem_par = fato_rows(db, "nivel_cruzamento_efd = 'EC_SEM_PAR'")
    assert len(sem_par) == 1
    r = sem_par[0]
    assert (r["origem"], r["cod_item"], r["cfop"]) == ("EC_C170_SEM_PAR", "P9", "1102")
    assert r["vl_pis"] == Decimal("1.65") and r["vl_cofins"] == Decimal("7.60")
    assert r["vl_contabil"] == 0 and r["status_efd"].startswith("Somente EFD")
    assert audit.run_check(db, "efd_sem_par").height == 1
    # as demais linhas continuam item a item
    assert fato_rows(db, f"cnpj_filial = '{A}' AND cod_item = 'P1' AND origem = 'SF_C170'")[0]["nivel"] == "N1_ITEM"
    assert_fechamento(db)
    db.close()


def test_codigo_de_item_diferente_mesma_posicao_e_valor(tmp_path):
    """Códigos de item divergentes entre os arquivos: posição + valor + CFOP iguais => N1V."""
    f = base_files()
    e = f["EFD.txt"]
    i1 = idx(e, "|C170|1|P1|")
    e[i1] = e[i1].replace("|C170|1|P1|", "|C170|1|X-P1|", 1)
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    r = fato_rows(db, f"cnpj_filial = '{A}' AND cod_item = 'P1' AND origem = 'SF_C170'")[0]
    assert r["nivel"] == "N1V_POSICAO_VALOR" and r["vl_pis"] == Decimal("16.50")
    assert_fechamento(db)
    db.close()


def test_valor_divergente_na_mesma_posicao_cai_para_n2(tmp_path):
    """Mesmo código e posição, valor do item diferente: não é N1; o crédito chega pelo N2 (COD_ITEM + CFOP)."""
    f = base_files()
    e = f["EFD.txt"]
    i1 = idx(e, "|C170|1|P1|")
    e[i1] = e[i1].replace("|UN|1000,00|", "|UN|990,00|", 1)
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    r = fato_rows(db, f"cnpj_filial = '{A}' AND cod_item = 'P1' AND origem = 'SF_C170'")[0]
    assert r["nivel"] == "N2_ITEM_CFOP" and r["vl_pis"] == Decimal("16.50")
    assert audit.run_check(db, "valor_item").height >= 1
    assert_fechamento(db)
    db.close()


def test_nota_duplicada_no_sped_fiscal_nao_duplica_credito(tmp_path):
    """A mesma chave escriturada duas vezes no SPED Fiscal: o crédito da EFD entra uma única vez."""
    f = base_files()
    s = f["SF_A.txt"]
    ini = idx(s, "|C100|0|1|FX|")
    fim = idx(s, "|C100|0|0|FY|")
    s[fim:fim] = s[ini:fim]          # duplica o bloco C100..C190/C191 da NF1
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    p1 = fato_rows(db, f"cnpj_filial = '{A}' AND cod_item = 'P1' AND origem = 'SF_C170'")
    assert len(p1) == 2
    assert sorted(str(r["nivel"]) for r in p1) == ["N1_ITEM", "None"]
    assert sum(r["vl_pis"] or 0 for r in p1) == Decimal("16.50")
    assert_fechamento(db)
    db.close()


def test_nota_da_efd_ausente_no_sped_fiscal(tmp_path):
    """Nota inteira só na EFD (filial com SPED Fiscal no período): itens entram como 'Somente EFD'."""
    f = base_files()
    s = f["SF_A.txt"]
    ini, fim = idx(s, "|C100|0|1|FX|"), idx(s, "|C100|0|0|FY|")
    del s[ini:fim]                   # remove a NF1 do SPED Fiscal
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    sem_par = fato_rows(db, "origem = 'EC_C170_SEM_PAR'")
    assert {r["cod_item"] for r in sem_par} == {"P1", "P2"}
    assert sum(r["vl_pis"] for r in sem_par) == Decimal("24.75")
    assert audit.run_check(db, "ec_sem_sf").height == 1
    assert_fechamento(db)
    db.close()


def test_nota_sem_chave_casa_por_numero(tmp_path):
    """Nota em papel (sem CHV_NFE nos dois arquivos): vínculo por fornecedor + modelo + série + número."""
    f = base_files()
    k = sd.chave(1001, sd.F_X, comp="2024-01")
    for name in f:
        f[name] = [l.replace(k, "") if l.startswith("|C100|") else l for l in f[name]]
    db = build(tmp_path, {k2: join(v) for k2, v in f.items()})
    r = fato_rows(db, f"cnpj_filial = '{A}' AND cod_item = 'P1' AND origem = 'SF_C170'")[0]
    assert r["nivel"] == "N1_ITEM" and r["vl_pis"] == Decimal("16.50")
    assert_fechamento(db)
    db.close()


def test_frete_sem_linha_analitica_no_sf_nao_some(tmp_path):
    """CT-e no SPED Fiscal sem D190: o crédito do D101/D105 não tem onde ser rateado e vira 'Somente EFD'."""
    f = base_files()
    s = f["SF_A.txt"]
    del s[idx(s, "|D190|")]
    db = build(tmp_path, {k: join(v) for k, v in f.items()})
    r = fato_rows(db, "origem = 'EC_D100_SEM_PAR'")
    assert len(r) == 1 and r[0]["vl_pis"] == Decimal("1.98")
    assert_fechamento(db)
    db.close()


def test_nota_escriturada_em_meses_diferentes(tmp_path):
    """Nota na EFD de janeiro e no SPED Fiscal de fevereiro: casa pela chave; reimportar/remover mantém coerência."""
    k = sd.chave(7777, sd.F_X, comp="2024-01")
    efd = lines_of(sd.efd_contrib("2024-01"))
    efd[idx(efd, "|C100|0|0|FY|"):idx(efd, "|C100|0|0|FY|")] = [
        f"|C100|0|1|FX|55|00|1|7777|{k}|30012024|02022024|400,00|0|0,00|0,00|400,00|9|0,00|0,00|0,00|400,00|72,00|"
        "0,00|0,00|0,00|6,60|30,40|||",
        "|C170|1|P1||40,00000|UN|400,00|0,00|0|000|1102||400,00|18,00|72,00|0,00|0,00|0,00|0|49||0,00|0,00|0,00|50|"
        "400,00|1,6500|||6,60|50|400,00|7,6000|||30,40|1.1.01|"]
    sf_fev = lines_of(sd.sped_fiscal(A, "SP", "2024-02"))
    sf_fev[idx(sf_fev, "|C100|0|0|FY|"):idx(sf_fev, "|C100|0|0|FY|")] = [
        f"|C100|0|1|FX|55|00|1|7777|{k}|30012024|02022024|400,00|0|0,00|0,00|400,00|9|0,00|0,00|0,00|400,00|72,00|"
        "0,00|0,00|0,00|||||",
        "|C170|1|P1||40,00000|UN|400,00|0,00|0|000|1102|N1|400,00|18,00|72,00|0,00|0,00|0,00|0|49|999|0,00|0,00|"
        "0,00||||||||||||||1.1.01||",
        "|C190|000|1102|18,00|400,00|400,00|72,00|0,00|0,00|0,00|0,00||"]
    # 1) só janeiro: a nota existe apenas na EFD
    db = build(tmp_path, {"SF_A_jan.txt": join(lines_of(sd.sped_fiscal(A, "SP", "2024-01"))), "EFD_jan.txt": join(efd)})
    assert len(fato_rows(db, "origem = 'EC_C170_SEM_PAR'")) == 1
    assert_fechamento(db)
    # 2) chega o SPED Fiscal de fevereiro: janeiro é reconsolidado junto e a sobra desaparece
    p = tmp_path / "SF_A_fev.txt"
    p.write_bytes(join(sf_fev))
    s = db.import_paths([p], workers=1)
    assert s.competencias_reconsolidadas == ["2024-01", "2024-02"]
    assert fato_rows(db, "origem = 'EC_C170_SEM_PAR'") == []
    r = fato_rows(db, "competencia = '2024-02' AND vl_item = 400")[0]
    assert r["nivel"] == "N1_ITEM" and r["vl_pis"] == Decimal("6.60")
    assert_fechamento(db)
    # 3) remover a EFD de janeiro reconsolida fevereiro (que dependia dela): o crédito sai
    fid = db.scalar("SELECT id_arquivo FROM sys_arquivos_importados WHERE tipo_sped = 'CONTRIB'")
    assert set(db.remove_files([fid])) == {"2024-01", "2024-02"}
    r = fato_rows(db, "competencia = '2024-02' AND vl_item = 400")[0]
    assert r["nivel"] is None and r["vl_pis"] is None
    assert db.scalar(f"SELECT coalesce(sum(vl_pis), 0) FROM {FATO}") == 0
    db.close()


def test_cenario_combinado_fecha(tmp_path):
    """Todas as distorções juntas, duas filiais, EFD individualizada + consolidada: o total fecha."""
    sf_a = lines_of(sd.sped_fiscal(A, "SP", "2024-01"))
    sf_b = lines_of(sd.sped_fiscal(B, "RJ", "2024-01"))
    e = lines_of(sd.efd_contrib("2024-01"))
    i1, i2 = idx(e, "|C170|1|P1|"), idx(e, "|C170|2|P2|", "|500,00|")
    e[i1] = e[i1].replace("|C170|1|P1|", "|C170|2|P1|", 1)
    e[i2] = e[i2].replace("|C170|2|P2|", "|C170|1|P2|", 1)
    e.insert(i2 + 1, "|C170|3|P9||1,00000|UN|100,00|0,00|0|000|1102||0,00|0,00|0,00|0,00|0,00|0,00|0|49||0,00|0,00|"
                     "0,00|50|100,00|1,6500|||1,65|50|100,00|7,6000|||7,60|1.1.01|")
    # consolidação C190 da filial B com um item que não existe no SPED Fiscal dela
    c195 = idx(e, "|C195|")
    e[c195 + 1:c195 + 1] = [f"|C190|55|01012024|31012024|P7|22030000||200,00|",
                            f"|C191|{sd.F_Y}|50|1102|200,00|0,00|200,00|1,6500|||3,30|1.1.01|",
                            f"|C195|{sd.F_Y}|50|1102|200,00|0,00|200,00|7,6000|||15,20|1.1.01|"]
    ini, fim = idx(sf_a, "|C100|0|1|FX|"), idx(sf_a, "|C100|0|0|FY|")
    sf_a[fim:fim] = sf_a[ini:fim]
    del sf_a[idx(sf_a, "|D190|")]
    db = build(tmp_path, {"SF_A.txt": join(sf_a), "SF_B.txt": join(sf_b), "EFD.txt": join(e)})
    assert_fechamento(db)
    origens = {r["origem"] for r in fato_rows(db, "nivel_cruzamento_efd = 'EC_SEM_PAR'")}
    assert origens == {"EC_C170_SEM_PAR", "EC_C190_SEM_PAR", "EC_D100_SEM_PAR"}
    diag = audit.run_check(db, "qualidade_cruzamento")
    assert {"N2_ITEM_CFOP", "N3_CONSOLIDADO_C190", "EC_SEM_PAR"} <= set(diag["nivel"].to_list())
    db.close()


# ------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def full(tmp_path_factory):
    base = tmp_path_factory.mktemp("agg")
    src = base / "src"
    sd.write_scenario(src)
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    db.import_paths([src], workers=1)
    yield db
    db.close()


@pytest.mark.parametrize("dims,gf,rules,esperado", [
    (["filial"], None, None, "agg_filial"),
    (["cfop"], {"competencias": ["2024-01"]}, None, "agg_filial"),
    (["competencia"], None, {"field": "cst_pis", "operator": "em", "value": "50,51"}, "agg_filial"),
    (["fornecedor"], {"filiais": [A]}, None, "agg_fornecedor"),
    (["filial", "fornecedor", "cfop"], None, None, "agg_fornecedor"),
    (["item"], None, None, "agg_produto"),
    (["ncm"], {"filiais": [A]}, {"field": "tipo_item", "operator": "=", "value": "00"}, "agg_produto"),
    (["fornecedor", "item"], None, None, "agg_item"),
    (["filial", "fornecedor", "cfop", "item"], {"ncm_prefixo": "2203"}, None, "agg_item"),
    (["filial"], None, {"field": "vl_icms", "operator": ">", "value": 0}, FATO),      # condição por linha
    (["filial"], None, {"field": "num_doc", "operator": "=", "value": "1001"}, FATO),  # coluna de documento
])
def test_agregadas_equivalem_a_fato(full, dims, gf, rules, esperado):
    """O roteador escolhe a menor tabela possível e o resultado é idêntico ao calculado linha a linha."""
    mets = analytics.DEFAULT_METRICS
    assert analytics.source_for(gf, rules, dims, mets) == esperado
    a = analytics.aggregate(full, gf, rules, dims, mets, limit=None).sort(dims)
    b = analytics.aggregate(full, gf, rules, dims, mets, limit=None, source=FATO).sort(dims)
    assert a.height == b.height and a.height > 0
    assert a.columns == b.columns
    for c in a.columns:
        if a[c].dtype.is_numeric():
            assert (a[c].fill_null(0) - b[c].fill_null(0)).abs().max() < 1e-6, c
        else:
            assert a[c].to_list() == b[c].to_list(), c


def test_contagem_de_documentos_usa_fato(full):
    assert analytics.source_for(None, None, ["filial"], ["vl_contabil", "n_docs"]) == FATO
    n = analytics.count_documents(full, None, None)
    assert n == full.scalar(f"SELECT count(DISTINCT doc_key) FROM {FATO}") and n > 0
    assert analytics.totals(full, None, None, ["n_linhas"])["n_linhas"] == full.scalar(f"SELECT count(*) FROM {FATO}")
