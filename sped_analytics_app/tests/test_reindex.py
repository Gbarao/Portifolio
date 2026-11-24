"""Arquivos importados antes de o programa guardar as linhas originais e que não estão mais no caminho original:
indexação a partir da pasta onde estão hoje (reconhecidos pelo hash) e reimportação dos mesmos arquivos."""
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app
from app.database.engine import SpedDatabase
from tests import sample_data as sd


def _old_db(base):
    """Base como a de uma versão anterior: importada, mas sem linhas originais, e TXT movidos de lugar."""
    src = base / "src"
    sd.write_scenario(src)
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    db.import_paths([src], workers=1)
    n_sf = db.scalar("SELECT count(*) FROM sf_linhas")
    n_ec = db.scalar("SELECT count(*) FROM ec_linhas")
    for t in ("sf_linhas", "ec_linhas", "linhas_contagem"):
        db.con.execute(f"DELETE FROM {t}")
    moved = base / "outro_lugar" / "subpasta"
    moved.parent.mkdir()
    shutil.move(str(src), str(moved))
    for i, p in enumerate(sorted(moved.rglob("*.txt"))):   # renomeados: o reconhecimento é pelo conteúdo
        p.rename(p.with_name(f"arquivo_{i}.txt"))
    return db, moved, n_sf, n_ec


def _wait(c, job):
    t0 = time.time()
    while c.get(f"/api/jobs/{job}").json()["status"] == "running" and time.time() - t0 < 120:
        time.sleep(0.1)
    return c.get(f"/api/jobs/{job}").json()


def test_indexar_pela_pasta_nova(tmp_path):
    db, moved, n_sf, n_ec = _old_db(tmp_path)
    try:
        with TestClient(create_app(db=db)) as c:
            pend = c.get("/api/raw/pending").json()
            assert len(pend) == 6 and not any(p["encontrado"] for p in pend)
            j = _wait(c, c.post("/api/raw/index", json={}).json()["job"])
            assert j["result"]["indexados"] == 0 and len(j["result"]["nao_encontrados"]) == 6
            assert c.post("/api/raw/index", json={"pastas": [str(tmp_path / "nao_existe")]}).status_code == 400
            j = _wait(c, c.post("/api/raw/index", json={"pastas": [str(moved.parent)]}).json()["job"])
            assert j["status"] == "done", j
            assert j["result"]["indexados"] == 6 and j["result"]["encontrados_na_pasta"] == 6
            assert j["result"]["nao_encontrados"] == [] and c.get("/api/raw/pending").json() == []
        assert db.scalar("SELECT count(*) FROM sf_linhas") == n_sf and db.scalar("SELECT count(*) FROM ec_linhas") == n_ec
        # caminho atualizado para o local novo; Bloco M volta a aparecer
        caminhos = [r[0] for r in db.con.execute("SELECT caminho_origem FROM sys_arquivos_importados").fetchall()]
        assert all("outro_lugar" in c and "arquivo_" in c for c in caminhos)
        from app.database import bloco_m
        assert bloco_m.analyze(db, {})["consolidacao"].height == 4
    finally:
        db.close()


def test_reimportar_guarda_as_linhas(tmp_path):
    db, moved, n_sf, n_ec = _old_db(tmp_path)
    try:
        fato0 = db.scalar("SELECT count(*) FROM fato_entradas_consolidadas")
        s = db.import_paths([moved], workers=1)
        assert s.count("INDEXADO") == 6 and s.count("IMPORTADO") == 0 and s.count("DUPLICADO") == 0
        assert db.files_without_lines() == []
        assert db.scalar("SELECT count(*) FROM sf_linhas") == n_sf and db.scalar("SELECT count(*) FROM ec_linhas") == n_ec
        assert db.scalar("SELECT count(*) FROM fato_entradas_consolidadas") == fato0   # consolidação intacta
        assert db.scalar("SELECT count(*) FROM sys_arquivos_importados") == 6           # nada duplicado
        # uma segunda reimportação volta a ser "duplicado"
        assert db.import_paths([moved], workers=1).count("DUPLICADO") == 6
    finally:
        db.close()
