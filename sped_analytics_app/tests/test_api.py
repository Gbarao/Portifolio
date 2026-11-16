"""Testes da API local (FastAPI) usada pela interface."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app
from app.database.engine import SpedDatabase
from tests import sample_data as sd


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    base = tmp_path_factory.mktemp("api")
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    app = create_app(db=db)
    with TestClient(app) as c:
        c.base = base  # type: ignore[attr-defined]
        yield c
    db.close()


def wait(client, jid, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.1)
    raise TimeoutError(jid)


def test_meta_e_interface(client):
    m = client.get("/api/meta").json()
    assert {d["key"] for d in m["dimensions"]} >= {"filial", "fornecedor", "cfop", "item"}
    assert any(c["key"] == "fechamento_efd" for c in m["checks"])
    r = client.get("/")
    assert r.status_code == 200 and "<div id=\"root\">" in r.text
    assert client.get("/analise/qualquer").status_code == 200        # rotas da SPA devolvem o index
    assert client.get("/api/inexistente").status_code in (404, 405)


def test_importacao_por_pasta_e_por_upload(client):
    src = client.base / "src"
    files = sd.write_scenario(src)
    jid = client.post("/api/hub/import", json={"paths": [str(src)], "workers": 1}).json()["job"]
    j = wait(client, jid)
    assert j["status"] == "done", j
    assert j["result"]["contagem"]["IMPORTADO"] == 6
    # mesmo arquivo enviado pela interface (upload) -> duplicado
    with open(files[0], "rb") as fh:
        jid = client.post("/api/hub/upload", files=[("files", (Path(files[0]).name, fh, "text/plain"))]).json()["job"]
    j = wait(client, jid)
    assert j["result"]["contagem"]["DUPLICADO"] == 1
    assert client.post("/api/hub/import", json={"paths": ["/caminho/que/nao/existe"]}).status_code == 400


def test_central_de_arquivos(client):
    s = client.get("/api/hub/stats").json()
    assert s["arquivos"] == 6 and s["linhas_fato"] > 0
    cov = client.get("/api/hub/coverage").json()
    assert cov["competencias"] == ["2024-01", "2024-02"]
    assert all(set(f["status"].values()) == {"AMBOS"} for f in cov["filiais"])
    f = client.get("/api/hub/files").json()
    assert len(f["rows"]) == 6 and "id_arquivo" in f["columns"]
    assert client.get("/api/hub/log").json()["rows"]


def test_arvore_niveis_e_totais(client):
    root = client.post("/api/aggregate", json={"dims": ["filial"], "metrics": ["vl_contabil", "vl_pis", "n_linhas"]}).json()
    assert root["source"] == "agg_filial" and len(root["rows"]) == 2
    ci = root["columns"].index("vl_contabil")
    assert abs(sum(r[ci] for r in root["rows"]) - root["totals"]["vl_contabil"]) < 0.005
    filial = root["rows"][0][root["columns"].index("filial")]
    lvl2 = client.post("/api/aggregate", json={"dims": ["fornecedor"], "metrics": ["vl_contabil"],
                                               "path": [["filial", filial]]}).json()
    assert lvl2["source"] == "agg_fornecedor" and "fornecedor__desc" in lvl2["columns"]
    piv = client.post("/api/pivot", json={"dims": ["filial"], "metric": "vl_contabil"}).json()
    assert {"2024-01", "2024-02", "TOTAL"} <= set(piv["columns"]) and piv["totals"]["TOTAL"] > 0
    tot = client.post("/api/totals", json={"metrics": ["vl_contabil", "n_linhas"]}).json()
    assert tot["totals"]["vl_contabil"] == pytest.approx(root["totals"]["vl_contabil"])
    assert client.post("/api/count-docs", json={}).json()["n"] > 0
    docs = client.post("/api/documents", json={"path": [["filial", sd.CNPJ_A], ["fornecedor", sd.F_X]]}).json()
    assert docs["rows"] and "chave" in docs["columns"]


def test_filtros_invalidos_viram_400(client):
    r = client.post("/api/aggregate", json={"dims": ["filial"], "rules": {"op": "AND", "rules": [
        {"field": "vl_icms; DROP TABLE x", "operator": "=", "value": 1}]}})
    assert r.status_code == 400 and "Filtro inválido" in r.json()["detail"]
    p = client.post("/api/rules/preview", json={"rules": {"op": "AND", "rules": [{"field": "cst_pis", "operator": "em", "value": "50,51"}]}}).json()
    assert p["ok"] and "IN" in p["sql"]


def test_filtros_salvos_snapshots_e_estado(client):
    fid = client.post("/api/filters", json={"nome": "PIS 50", "categoria": "PIS/COFINS",
                                            "definicao": {"rules": {"op": "AND", "rules": [{"field": "cst_pis", "operator": "=", "value": "50"}]}}}).json()["id"]
    assert any(f["id"] == fid for f in client.get("/api/filters").json())
    assert client.delete(f"/api/filters/{fid}").json()["ok"]
    st = {"gf": {"competencias": ["2024-01"]}, "rules": {"op": "AND", "rules": []}, "hierarchy": ["filial", "fornecedor"],
          "metrics": ["vl_contabil"], "mode": "arvore", "pivotMetric": "vl_contabil", "appliedFilterName": "", "page": "analise"}
    assert client.put("/api/state", json=st).json()["ok"]
    assert client.get("/api/state").json()["hierarchy"] == ["filial", "fornecedor"]
    sid = client.post("/api/snapshots", json={"nome": "Teste", "anotacoes": "x", "state": st}).json()["id"]
    snap = client.get(f"/api/snapshots/{sid}").json()
    assert snap["ok"] and snap["total"] > 0 and snap["meta"]["contexto"]["state"]["hierarchy"] == ["filial", "fornecedor"]
    exp = client.post(f"/api/snapshots/{sid}/export").json()
    assert client.get(exp["url"]).status_code == 200
    assert client.delete(f"/api/snapshots/{sid}").json()["ok"]


def test_migracao_do_estado_da_interface_antiga(client):
    client.app.state.db.session_set("ui_state", {"global_filters": {"filiais": [sd.CNPJ_A]}, "mode": "plana",
                                                 "metrics": ["vl_contabil", "n_docs"], "hierarchy": ["filial"]})
    st = client.get("/api/state").json()
    assert st["v"] == 3 and st["mode"] == "tabela" and st["gf"] == {"filiais": [sd.CNPJ_A]} and st["metrics"] == ["vl_contabil"]


def test_exportacoes(client):
    for url, body in (("/api/export/summary", {"hierarchy": ["filial", "fornecedor"]}),
                      ("/api/export/summary", {"hierarchy": ["filial"], "mode": "mensal"}),
                      ("/api/export/lines", {"fmt": "xlsx"}), ("/api/export/lines", {"fmt": "csv"}),
                      ("/api/export/lines", {"fmt": "parquet"}),
                      ("/api/export/documents", {"path": [["filial", sd.CNPJ_A]]}),
                      ("/api/export/audit", {})):
        r = client.post(url, json=body)
        assert r.status_code == 200, (url, r.text)
        d = client.get(r.json()["url"])
        assert d.status_code == 200 and len(d.content) > 100, url
    assert client.get("/api/download/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_auditoria(client):
    s = client.post("/api/audit/summary", json={}).json()["items"]
    by = {i["verificacao"]: i["ocorrencias"] for i in s}
    assert by["fechamento_efd"] == 0
    d = client.post("/api/audit/check", json={"check": "qualidade_cruzamento"}).json()
    assert d["total"] > 0 and "nivel" in d["columns"]


def test_backup_e_remocao(client):
    j = wait(client, client.post("/api/hub/backup", json={}).json()["job"])
    assert j["status"] == "done" and client.get(j["result"]["url"]).status_code == 200
    j = wait(client, client.post("/api/hub/remove-competencias", json={"competencias": ["2024-02"], "tipo": "CONTRIB"}).json()["job"])
    assert j["status"] == "done"
    cov = client.get("/api/hub/coverage").json()
    assert {f["status"]["2024-02"] for f in cov["filiais"]} == {"SF"}
    j = wait(client, client.post("/api/hub/rebuild").json()["job"])
    assert j["status"] == "done" and j["result"]["linhas"] > 0
