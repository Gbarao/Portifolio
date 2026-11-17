"""Relatório dinâmico: qualquer combinação de linhas/colunas/valores fecha com a base, sem duplicidade."""
import itertools
import time

import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app
from app.database import analytics as A
from app.database.aggregates import FATO
from app.database.engine import SpedDatabase
from tests import sample_data as sd

M = ["vl_contabil", "vl_icms", "vl_icms_st_fcp", "vl_ipi", "vl_pis", "vl_cofins", "vl_trib_recuperaveis", "qtd"]
DIMS = ["filial", "fornecedor", "cfop", "descr_item", "item", "competencia", "cst_pis", "origem"]


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("rep")
    sd.write_scenario(base / "src")
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    db.import_paths([base / "src"], workers=1)
    with TestClient(create_app(db=db)) as c:
        yield {"db": db, "c": c}
    db.close()


def base_totals(db):
    return {m: float(db.scalar(f"SELECT coalesce(sum({e}), 0) FROM {FATO}") or 0)
            for m, e in (("vl_contabil", "vl_contabil"), ("vl_pis", "vl_pis"), ("vl_cofins", "vl_cofins"),
                         ("vl_icms", "vl_icms"), ("qtd", "qtd"))}


@pytest.mark.parametrize("rows", [list(c) for n in (1, 2, 3, 4) for c in itertools.combinations(DIMS, n)][:60])
def test_qualquer_combinacao_fecha_sem_duplicidade(env, rows):
    """A soma das linhas exibidas = total da base = total devolvido, para qualquer combinação de dimensões."""
    db = env["db"]
    r = A.report(db, None, None, rows, None, M, limit=None)
    bt = base_totals(db)
    for m in ("vl_contabil", "vl_pis", "vl_cofins", "vl_icms", "qtd"):
        soma = float(r["df"][m].fill_null(0).sum())
        assert soma == pytest.approx(bt[m], abs=0.005), (rows, m)
        assert r["totals"][m] == pytest.approx(bt[m], abs=0.005)
    assert r["row_count"] == r["df"].height
    # cada combinação de chaves aparece uma única vez
    keys = [d for d in rows]
    assert r["df"].select(keys).is_unique().all()


def test_pis_cofins_do_relatorio_igual_a_efd(env):
    db = env["db"]
    efd = float(db.scalar("""SELECT sum(v) FROM (SELECT sum(vl_pis) v FROM ec_item
        UNION ALL SELECT sum(vl) FROM ec_doc_trib WHERE tributo='PIS' UNION ALL SELECT sum(vl) FROM ec_c191_195 WHERE tributo='PIS'
        UNION ALL SELECT sum(vl_pis) FROM ec_f)"""))
    r = A.report(db, None, None, ["filial", "fornecedor", "cfop", "descr_item"], None, ["vl_pis"])
    assert r["totals"]["vl_pis"] == pytest.approx(efd, abs=0.005)


def test_colunas_cruzadas(env):
    db = env["db"]
    r = A.report(db, None, None, ["filial", "fornecedor"], "competencia", ["vl_contabil", "vl_pis"], limit=None)
    df = r["df"]
    meses = [cm["key"] for cm in r["columns_meta"] if cm["metric"] == "vl_contabil" and cm["group"] != "TOTAL"]
    assert len(meses) == 2
    for row in df.to_dicts():
        assert sum(row[k] or 0 for k in meses) == pytest.approx(row["TOTAL␟vl_contabil"], abs=0.005)
    assert r["totals"]["TOTAL␟vl_contabil"] == pytest.approx(base_totals(db)["vl_contabil"], abs=0.005)
    assert sum(r["totals"][k] for k in meses) == pytest.approx(r["totals"]["vl_contabil"], abs=0.005)
    with pytest.raises(A.ReportError):
        A.report(db, None, None, ["filial"], "filial", ["vl_contabil"])


def test_ordenacao_limite_texto_e_filtro_por_valor(env):
    db = env["db"]
    asc = A.report(db, None, None, ["fornecedor"], None, ["vl_contabil"], sort={"by": "vl_contabil", "dir": "asc"})
    v = asc["df"]["vl_contabil"].to_list()
    assert v == sorted(v)
    desc = A.report(db, None, None, ["fornecedor"], None, ["vl_contabil"], sort={"by": "vl_contabil", "dir": "desc"}, limit=2)
    assert desc["truncated"] and desc["df"].height == 2 and desc["df"]["vl_contabil"].to_list() == sorted(v, reverse=True)[:2]
    assert desc["totals"]["vl_contabil"] == pytest.approx(sum(v))           # total real, não o da tela
    az = A.report(db, None, None, ["descr_item"], None, ["vl_contabil"], sort={"by": "descr_item", "dir": "asc"})
    nomes = [x for x in az["df"]["descr_item"].to_list() if x is not None]
    assert nomes == sorted(nomes)
    t = A.report(db, None, None, ["filial", "fornecedor", "descr_item"], None, ["vl_contabil"], texto="cerveja")
    assert set(t["df"]["descr_item"].to_list()) == {"CERVEJA LATA"}
    z = A.report(db, None, None, ["filial", "fornecedor"], None, ["vl_contabil", "vl_pis"],
                 having=[{"metric": "vl_pis", "op": "zero"}, {"metric": "vl_contabil", "op": ">", "value": "300"}])
    assert all(x == 0 for x in z["df"]["vl_pis"].to_list()) and all(x > 300 for x in z["df"]["vl_contabil"].to_list())
    assert z["totals"]["vl_contabil"] == pytest.approx(float(z["df"]["vl_contabil"].sum()), abs=0.005)


def test_api_e_exportacao(env):
    c = env["c"]
    body = {"rows": ["filial", "fornecedor", "cfop", "descr_item"], "metrics": ["vl_contabil", "vl_icms", "vl_pis", "vl_cofins"],
            "sort": {"by": "vl_contabil", "dir": "desc"}, "texto": "", "having": []}
    r = c.post("/api/report", json=body).json()
    assert r["columns"][:6] == ["filial", "filial__desc", "fornecedor", "fornecedor__desc", "cfop", "descr_item"]
    assert r["labels"]["descr_item"] == "Descrição do item" and r["rowCount"] == len(r["rows"])
    r2 = c.post("/api/report", json={**body, "col": "competencia"}).json()
    assert any(cm["group"] == "TOTAL" for cm in r2["columnsMeta"])
    assert c.post("/api/report", json={**body, "metrics": []}).status_code == 400
    for b in (body, {**body, "col": "competencia"}):
        e = c.post("/api/export/report", json=b)
        assert e.status_code == 200, e.text
        assert c.get(e.json()["url"]).status_code == 200
