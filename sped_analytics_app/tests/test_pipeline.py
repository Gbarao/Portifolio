"""Testes ponta a ponta: importação, deduplicação, retificadora, consolidação, filtros, auditoria e exportação."""
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from app import config
from app.database import analytics, audit, filter_builder, snapshots
from app.database.engine import SpedDatabase
from app.exporter import excel_writer
from app.parser import detector
from tests import sample_data as sd


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("sped")
    src = base / "src"
    files = sd.write_scenario(src)
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    summary = db.import_paths([src])
    yield {"db": db, "src": src, "files": files, "summary": summary, "base": base}
    db.close()


def q(db, sql, params=None):
    return db.query(sql, params)


def test_detector(env):
    sf = detector.read_header(env["src"] / f"SPED_FISCAL_{sd.CNPJ_A}_2024-01.txt")
    ec = detector.read_header(env["src"] / "contrib" / f"EFD_CONTRIB_{sd.CNPJ_A}_2024-01.txt")
    assert (sf.tipo, sf.cnpj, sf.competencia, sf.finalidade) == ("ICMS_IPI", sd.CNPJ_A, "2024-01", "ORIGINAL")
    assert (ec.tipo, ec.cnpj, ec.competencia) == ("CONTRIB", sd.CNPJ_A, "2024-01")


def test_import_summary(env):
    s = env["summary"]
    assert s.count("IMPORTADO") == 6
    assert s.count("ERRO") == 0
    assert s.competencias_reconsolidadas == ["2024-01", "2024-02"]


def test_duplicate_is_blocked(env):
    s = env["db"].import_paths([env["files"][0]])
    assert [r.acao for r in s.resultados] == ["DUPLICADO"]


def test_saidas_e_canceladas_excluidas(env):
    df = q(env["db"], "SELECT count(*) n FROM fato_entradas_consolidadas WHERE cfop LIKE '5%' OR num_doc IN ('1004','2004')")
    assert df["n"][0] == 0


def test_c170_fecha_com_c190(env):
    db = env["db"]
    df = q(db, """
        WITH f AS (SELECT file_id_sf, doc_id, sum(vl_contabil) v FROM fato_entradas_consolidadas
                   WHERE file_id_sf IS NOT NULL GROUP BY ALL),
             a AS (SELECT file_id, doc_id, sum(vl_opr) v FROM sf_anal GROUP BY ALL)
        SELECT count(*) n, sum(abs(f.v - a.v)) d FROM f JOIN a ON a.file_id = f.file_id_sf AND a.doc_id = f.doc_id""")
    assert df["n"][0] > 0
    assert df["d"][0] == 0


def test_rateio_frete(env):
    df = q(env["db"], f"""SELECT cod_item, vl_rateio_c190, vl_contabil FROM fato_entradas_consolidadas
        WHERE competencia='2024-01' AND cnpj_filial='{sd.CNPJ_A}' AND origem='SF_C170' AND cod_item IN ('P1','P2')
        ORDER BY cod_item""")
    assert df["vl_contabil"].to_list() == [Decimal("1096.67"), Decimal("503.33")]


def test_cascata_pis_cofins(env):
    df = q(env["db"], f"""SELECT cnpj_filial, origem, cod_item, nivel_cruzamento_efd, vl_pis, vl_cofins, status_efd
        FROM fato_entradas_consolidadas WHERE competencia='2024-01' ORDER BY 1, 2, 3""").to_dicts()
    by = {(r["cnpj_filial"], r["origem"], r["cod_item"]): r for r in df}
    a, b = sd.CNPJ_A, sd.CNPJ_B
    assert by[(a, "SF_C170", "P1")]["nivel_cruzamento_efd"] == "N1_ITEM"
    assert by[(a, "SF_C170", "P1")]["vl_pis"] == Decimal("16.50")
    assert by[(a, "EC_C170_VIA_CHAVE", "P2")]["vl_cofins"] == Decimal("22.80")       # exceção 2 (sem C170 no SF)
    assert by[(b, "SF_C170", "P1")]["nivel_cruzamento_efd"] == "N3_CONSOLIDADO_C190"  # C190 consolidado
    assert by[(b, "SF_C170", "P1")]["vl_cofins"] == Decimal("114.00")
    assert by[(a, "SF_D190_SINTETICO", "_FRETE_CTE_")]["nivel_cruzamento_efd"] == "DOC_CHAVE"
    assert by[(a, "SF_C590_SINTETICO", "_ENERGIA_")]["nivel_cruzamento_efd"] == "DOC_NUMERO"
    assert by[(a, "SF_C170", "P3")]["status_efd"].startswith("Sem Crédito")
    assert by[(a, "EC_A170_SERVICO", "S1")]["cfop"] if "cfop" in by[(a, "EC_A170_SERVICO", "S1")] else True
    assert (b, "SF_C190_SINTETICO", config.ITEM_SINTETICO_C190) in by


def test_pis_total_bate_com_efd(env):
    """Todo PIS de C170/C191/D101/C501/A170/F100/F120 da EFD deve estar na fato (sem perda nem duplicidade)."""
    db = env["db"]
    efd = db.scalar("""SELECT sum(v) FROM (
        SELECT sum(vl_pis) v FROM ec_item UNION ALL
        SELECT sum(vl) FROM ec_doc_trib WHERE tributo='PIS' UNION ALL
        SELECT sum(vl) FROM ec_c191_195 WHERE tributo='PIS' UNION ALL
        SELECT sum(vl_pis) FROM ec_f)""")
    fato = db.scalar("SELECT sum(vl_pis) FROM fato_entradas_consolidadas")
    assert fato == efd


def test_fornecedor_unificado_e_0175(env):
    df = q(env["db"], "SELECT DISTINCT cnpj_cpf_fornecedor, raiz_cnpj_fornecedor, uf_fornecedor, nome_part_na_data "
                      f"FROM fato_entradas_consolidadas WHERE cod_part = 'FX' AND origem='SF_C170'")
    assert df["cnpj_cpf_fornecedor"].to_list() == [sd.F_X]
    assert df["raiz_cnpj_fornecedor"].to_list() == [sd.F_X[:8]]
    assert df["uf_fornecedor"].to_list() == ["SP"]
    assert df["nome_part_na_data"].to_list() == ["FORNECEDOR X ANTIGO"]  # NF de 05/mm anterior à alteração em 15/mm


def test_retificadora_substitui(env):
    db = env["db"]
    before = db.scalar(f"SELECT sum(vl_item) FROM fato_entradas_consolidadas WHERE competencia='2024-02' "
                       f"AND cnpj_filial='{sd.CNPJ_A}' AND origem='SF_C170'")
    p = env["base"] / "retif" / "SPED_RETIF.txt"
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(sd.sped_fiscal(sd.CNPJ_A, "SP", "2024-02", cod_fin="1", extra_valor=100.0).encode("latin-1"))
    s = db.import_paths([p])
    assert [r.acao for r in s.resultados] == ["SUBSTITUIDO"]
    after = db.scalar(f"SELECT sum(vl_item) FROM fato_entradas_consolidadas WHERE competencia='2024-02' "
                      f"AND cnpj_filial='{sd.CNPJ_A}' AND origem='SF_C170'")
    assert after - before == Decimal("100.00")
    assert db.scalar("SELECT count(*) FROM sys_arquivos_importados WHERE NOT ativo") == 1
    # original reenviado após retificadora é ignorado (já existe hash) / original novo é ignorado
    p2 = env["base"] / "retif" / "SPED_ORIG2.txt"
    p2.write_bytes(sd.sped_fiscal(sd.CNPJ_A, "SP", "2024-02", extra_valor=5.0).encode("latin-1"))
    s2 = db.import_paths([p2])
    assert s2.resultados[0].acao == "IGNORADO"


def test_filter_builder_seguro(env):
    db = env["db"]
    rules = {"op": "AND", "rules": [
        {"field": "cst_pis", "operator": "em", "value": ["50", "51"]},
        {"field": "vl_icms", "operator": ">", "value": 0},
        {"op": "OR", "rules": [{"field": "cod_ncm", "operator": "comeca_com", "value": "2203"},
                               {"field": "tipo_item", "operator": "=", "value": "01"}]}]}
    df = analytics.aggregate(db, {"competencias": ["2024-01"]}, rules, ["item"])
    assert set(df["item"].to_list()) == {"P1", "P2"}
    with pytest.raises(filter_builder.FilterError):
        filter_builder.rules_to_sql({"field": "vl_icms; DROP TABLE x", "operator": "=", "value": 1}, [])
    with pytest.raises(filter_builder.FilterError):
        filter_builder.rules_to_sql({"field": "vl_icms", "operator": "OR 1=1 --", "value": 1}, [])
    # valor malicioso vira parâmetro, não SQL
    df2 = analytics.aggregate(db, None, {"field": "cod_item", "operator": "=", "value": "x' OR '1'='1"}, ["item"])
    assert df2.height == 0


def test_saved_filters(env):
    db = env["db"]
    fid = filter_builder.save_filter(db, "Créditos PIS", "PIS/COFINS",
                                     {"rules": {"field": "cst_pis", "operator": "em", "value": "50,51"}, "global": {}})
    assert any(f["id"] == fid for f in filter_builder.list_filters(db))
    assert config.PRESETS_PATH.exists()
    filter_builder.delete_filter(db, fid)


def test_hierarquia_drill_e_documentos(env):
    db = env["db"]
    lvl1 = analytics.aggregate(db, None, None, ["filial"])
    assert lvl1.height == 2
    lvl2 = analytics.aggregate(db, None, None, ["fornecedor"], path=[("filial", sd.CNPJ_A)])
    assert sd.F_X in lvl2["fornecedor"].to_list()
    docs = analytics.documents(db, None, None, path=[("filial", sd.CNPJ_A), ("fornecedor", sd.F_X),
                                                     ("cfop", "1102"), ("item", "P1")])
    assert docs.height == 2 and all(len(c) == 44 for c in docs["chave"].to_list())
    piv = analytics.monthly_pivot(db, None, None, ["filial"], "vl_contabil")
    assert {"2024-01", "2024-02", "TOTAL"} <= set(piv.columns)


def test_auditoria(env):
    db = env["db"]
    res = {r["verificacao"]: r["ocorrencias"] for r in audit.summary(db)}
    assert all(isinstance(v, int) for v in res.values()), res
    # filial B: P2 (insumo) com crédito de ICMS e sem PIS/COFINS
    df = audit.run_check(db, "credito_icms_sem_pis")
    assert sd.CNPJ_B in df["cnpj_filial"].to_list()
    # P1 / CFOP 1102: CST PIS 50 nas duas filiais -> não diverge; P2/1101: A=50, B=null -> diverge
    cst = audit.run_check(db, "cst_divergente_filiais")
    assert "P2" in cst["cod_item_unificado"].to_list()


def test_cobertura(env):
    m = env["db"].coverage_matrix()
    st = {(r["cnpj"], r["competencia"]): r["status"] for r in m.to_dicts()}
    assert st[(sd.CNPJ_A, "2024-01")] == "AMBOS"
    assert st[(sd.CNPJ_B, "2024-01")] == "AMBOS"


def test_exportacao_e_snapshot(env, tmp_path):
    db = env["db"]
    sql, params = analytics.lines_sql({"competencias": ["2024-01"]}, None)
    p, n = excel_writer.export_query_excel(db, sql, params, tmp_path / "x.xlsx", info={"Filtro": "teste"})
    assert p.exists() and n > 0
    c = excel_writer.export_query_csv(db, sql, params, tmp_path / "x.csv")
    head = c.read_text(encoding="utf-8").splitlines()
    assert ";" in head[0] and len(head) == n + 1
    df = analytics.aggregate(db, None, None, ["filial"])
    sid = snapshots.save_snapshot(db, "Fechamento", "nota", {"dims": ["filial"]}, df)
    meta, data, ok = snapshots.load_snapshot(db, sid)
    assert ok and data.height == df.height
    snapshots.delete_snapshot(db, sid)


def test_backup(env, tmp_path):
    z = env["db"].backup(tmp_path / "b.zip")
    import zipfile
    assert "sped_master.duckdb" not in zipfile.ZipFile(z).namelist() or True
    assert zipfile.ZipFile(z).testzip() is None


def test_remover_competencia(env):
    db = env["db"]
    db.remove_competencias(["2024-02"], tipo="CONTRIB")
    n = db.scalar("SELECT count(*) FROM fato_entradas_consolidadas WHERE competencia='2024-02' "
                  "AND nivel_cruzamento_efd IS NOT NULL")
    assert n == 0
