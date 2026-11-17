"""Consulta direta dos arquivos (telas SPED Fiscal / EFD-Contribuições): o que está no TXT, sem cruzamento."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app
from app.database.engine import SpedDatabase
from tests import sample_data as sd


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("raw")
    src = base / "src"
    files = sd.write_scenario(src)
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    db.import_paths([src], workers=1)
    with TestClient(create_app(db=db)) as c:
        yield {"c": c, "db": db, "files": files, "base": base}
    db.close()


def txt_lines(path: Path) -> list[str]:
    out = []
    for l in path.read_text(encoding="latin-1").splitlines():
        if l.startswith("|"):
            out.append(l)
        if l.startswith("|9999|"):
            break
    return out


def sf_file(env, cnpj=sd.CNPJ_A, comp="2024-01"):
    return next(p for p in env["files"] if p.name == f"SPED_FISCAL_{cnpj}_{comp}.txt")


def test_todas_as_linhas_guardadas_exatamente(env):
    db = env["db"]
    for p in env["files"]:
        fid = db.scalar("SELECT id_arquivo FROM sys_arquivos_importados WHERE caminho_origem = ?", [str(p.resolve())])
        tipo = db.scalar("SELECT tipo_sped FROM sys_arquivos_importados WHERE id_arquivo = ?", [fid])
        t = "sf_linhas" if tipo == "ICMS_IPI" else "ec_linhas"
        got = [r[0] for r in db.con.execute(f"SELECT linha FROM {t} WHERE file_id = ? ORDER BY line_no", [fid]).fetchall()]
        assert got == txt_lines(p), p.name
    # o Parquet das linhas não fica duplicado no cache
    assert not list((env["base"] / "pq" / "sf_linhas").glob("*.parquet"))


def test_visao_geral_e_registros(env):
    c = env["c"]
    o = c.get("/api/raw/ICMS_IPI/overview").json()
    assert len(o["arquivos"]) == 4 and all(f["indexado"] for f in o["arquivos"])
    assert {u["cnpj"] for u in o["unidades"]} == {sd.CNPJ_A, sd.CNPJ_B}
    regs = {r["reg"]: r for r in c.post("/api/raw/ICMS_IPI/registers", json={"competencias": ["2024-01"]}).json()}
    # todos os C100 do arquivo, inclusive a saída e a nota cancelada (que o cruzamento ignora)
    assert regs["C100"]["n"] == 2 * 5 and regs["C100"]["descricao"]
    assert regs["0000"]["n"] == 2 and regs["9999"]["n"] == 2
    ec = {r["reg"]: r["n"] for r in c.post("/api/raw/CONTRIB/registers", json={"unidades": [sd.CNPJ_B]}).json()}
    assert set(ec) >= {"C010", "C190", "C191", "C195", "0140"} and "A170" not in ec   # A170 é da matriz


def test_consulta_c100_com_saidas_e_canceladas(env):
    c = env["c"]
    q = {"reg": "C100", "competencias": ["2024-01"], "unidades": [sd.CNPJ_A]}
    r = c.post("/api/raw/ICMS_IPI/query", json=q).json()
    assert r["total"] == 5
    cols = r["columns"]
    rows = [dict(zip(cols, x)) for x in r["rows"]]
    assert [x["NUM_DOC"] for x in rows] == ["1001", "1002", "1003", "1004", "1005"]
    assert {x["COD_SIT"] for x in rows} == {"00", "02"}
    assert rows[0]["VL_DOC"] == 1600.0 and rows[0]["DT_DOC"] == "2024-01-05"
    assert rows[0]["part_nome"] == "FORNECEDOR X LTDA" and rows[0]["part_cnpj_cpf"] == sd.F_X
    assert rows[0]["linha_original"].startswith("|C100|0|1|FX|55|00|1|1001|")
    s = c.post("/api/raw/ICMS_IPI/query", json={**q, "operacao": "1"}).json()
    assert s["total"] == 1 and dict(zip(s["columns"], s["rows"][0]))["IND_OPER"] == "1"


def test_registro_filho_com_contexto_do_documento(env):
    c = env["c"]
    r = c.post("/api/raw/ICMS_IPI/query", json={"reg": "C170", "competencias": ["2024-01"], "unidades": [sd.CNPJ_A]}).json()
    assert r["docReg"] == "C100" and r["labels"]["doc_num_doc"] == "C100 · NUM_DOC"
    assert r["columns"][:5] == ["competencia", "unidade", "linha_no", "doc_num_doc", "NUM_ITEM"]
    rows = [dict(zip(r["columns"], x)) for x in r["rows"]]
    assert len(rows) == 4     # 2 itens NF1 + 1 item NF3 + 1 item da saída
    first = rows[0]
    assert first["doc_num_doc"] == "1001" and first["COD_ITEM"] == "P1" and first["item_descr"] == "CERVEJA LATA"
    assert first["part_nome"] == "FORNECEDOR X LTDA" and first["CFOP"] == "1102" and first["VL_ITEM"] == 1000.0
    # filtro de operação aplicado pelo documento-pai: só o item da saída
    s = c.post("/api/raw/ICMS_IPI/query", json={"reg": "C170", "competencias": ["2024-01"], "unidades": [sd.CNPJ_A],
                                               "operacao": "1"}).json()
    assert s["total"] == 1 and dict(zip(s["columns"], s["rows"][0]))["CFOP"] == "5102"


def test_condicoes_e_busca(env):
    c = env["c"]
    base = {"reg": "C170", "unidades": [sd.CNPJ_A]}
    r = c.post("/api/raw/ICMS_IPI/query", json={**base, "condicoes": [{"campo": "CFOP", "op": "em", "valor": "1101, 1556"}]}).json()
    assert r["total"] == 4 and {dict(zip(r["columns"], x))["CFOP"] for x in r["rows"]} == {"1101", "1556"}
    r = c.post("/api/raw/ICMS_IPI/query", json={**base, "condicoes": [{"campo": "VL_ITEM", "op": ">", "valor": "500"}]}).json()
    assert {dict(zip(r["columns"], x))["COD_ITEM"] for x in r["rows"]} == {"P1"}
    r = c.post("/api/raw/ICMS_IPI/query", json={**base, "busca": "p3"}).json()
    assert r["total"] == 2
    bad = c.post("/api/raw/ICMS_IPI/query", json={**base, "condicoes": [{"campo": "X'; DROP", "op": "=", "valor": 1}]})
    assert bad.status_code == 400
    assert c.post("/api/raw/ICMS_IPI/query", json={"reg": "C1'00"}).status_code == 400


def test_efd_por_estabelecimento_e_bloco_m(env):
    c = env["c"]
    r = c.post("/api/raw/CONTRIB/query", json={"reg": "C191", "unidades": [sd.CNPJ_B], "competencias": ["2024-01"]}).json()
    rows = [dict(zip(r["columns"], x)) for x in r["rows"]]
    assert len(rows) == 1 and rows[0]["CNPJ_CPF_PART"] == sd.F_X and rows[0]["VL_PIS"] == 24.75
    assert rows[0]["unidade"] == sd.CNPJ_B and r["docReg"] == "C190"
    a = c.post("/api/raw/CONTRIB/query", json={"reg": "A170"}).json()
    assert a["total"] == 2 and {dict(zip(a["columns"], x))["unidade"] for x in a["rows"]} == {sd.CNPJ_A}


def test_registro_desconhecido_campos_genericos(env):
    c = env["c"]
    r = c.post("/api/raw/CONTRIB/query", json={"reg": "0110"}).json()
    assert "COD_INC_TRIB" in r["columns"]
    # registro fora do catálogo: campos numerados, conteúdo preservado
    db = env["db"]
    fid = db.scalar("SELECT min(id_arquivo) FROM sys_arquivos_importados WHERE tipo_sped='CONTRIB'")
    db.con.execute("INSERT INTO ec_linhas VALUES (?, 9001, 'Z123', NULL, NULL, '|Z123|abc|1,50|')", [fid])
    r = c.post("/api/raw/CONTRIB/query", json={"reg": "Z123"}).json()
    row = dict(zip(r["columns"], r["rows"][0]))
    assert row["CAMPO_02"] == "abc" and row["CAMPO_03"] == "1,50" and row["linha_original"] == "|Z123|abc|1,50|"
    db.con.execute("DELETE FROM ec_linhas WHERE reg = 'Z123'")


def test_arquivo_completo_e_paginacao(env):
    c = env["c"]
    p = sf_file(env)
    fid = env["db"].scalar("SELECT id_arquivo FROM sys_arquivos_importados WHERE caminho_origem = ?", [str(p.resolve())])
    lines = txt_lines(p)
    r = c.post("/api/raw/ICMS_IPI/lines", json={"arquivo": fid, "limit": 10}).json()
    assert r["total"] == len(lines) and [x[3] for x in r["rows"]] == lines[:10]
    r2 = c.post("/api/raw/ICMS_IPI/lines", json={"arquivo": fid, "limit": 10, "offset": 10}).json()
    assert [x[3] for x in r2["rows"]] == lines[10:20]
    r3 = c.post("/api/raw/ICMS_IPI/lines", json={"arquivo": fid, "registros": ["C190"]}).json()
    assert r3["total"] == sum(1 for l in lines if l.startswith("|C190|"))


def test_exportacao(env):
    c = env["c"]
    for body in ({"reg": "C170", "fmt": "xlsx"}, {"reg": "C100", "fmt": "csv", "operacao": "0"},
                 {"modo": "arquivo", "arquivo": 1, "fmt": "xlsx"}):
        r = c.post("/api/raw/ICMS_IPI/export", json=body)
        assert r.status_code == 200, r.text
        assert c.get(r.json()["url"]).status_code == 200

def test_indexar_arquivos_antigos(env, tmp_path):
    """Arquivos importados antes desta versão (sem linhas originais) são indexados lendo o TXT de novo."""
    db = env["db"]
    fid = db.scalar("SELECT min(id_arquivo) FROM sys_arquivos_importados WHERE tipo_sped='ICMS_IPI'")
    n0 = db.scalar("SELECT count(*) FROM sf_linhas WHERE file_id = ?", [fid])
    db.con.execute("DELETE FROM sf_linhas WHERE file_id = ?", [fid])
    db.con.execute("DELETE FROM linhas_contagem WHERE file_id = ?", [fid])
    pend = db.files_without_lines()
    assert [p["id"] for p in pend] == [fid] and pend[0]["encontrado"]
    r = env["c"].post("/api/raw/index").json()
    t0 = time.time()
    while env["c"].get(f"/api/jobs/{r['job']}").json()["status"] == "running" and time.time() - t0 < 60:
        time.sleep(0.1)
    j = env["c"].get(f"/api/jobs/{r['job']}").json()
    assert j["status"] == "done" and j["result"]["indexados"] == 1
    assert db.scalar("SELECT count(*) FROM sf_linhas WHERE file_id = ?", [fid]) == n0
    assert db.files_without_lines() == []
