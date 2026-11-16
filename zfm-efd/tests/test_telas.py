"""Abre todas as telas (Streamlit AppTest) sobre a base sintetica: nenhuma pode dar erro."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

TELAS = sorted(p.name for p in (Path(__file__).resolve().parent.parent / "telas").glob("*.py"))


@pytest.fixture
def base_padrao(con_param, tmp_path):
    """Copia a base sintetica (com parametros) para o local padrao do programa (ZFM_DATA_DIR)."""
    from zfm.config import caminho_banco
    con_param.execute("CHECKPOINT")
    origem = con_param.execute("SELECT path FROM duckdb_databases() WHERE database_name = current_database()"
                               ).fetchall()[0][0]
    con_param.close()
    shutil.copyfile(origem, caminho_banco())
    return caminho_banco()


@pytest.mark.parametrize("tela", TELAS)
def test_tela_abre_sem_erro(base_padrao, tela):
    from streamlit.testing.v1 import AppTest
    raiz = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(raiz / "telas" / tela), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    erros = [e.value for e in at.error]
    assert not erros, erros
    textos = " ".join(m.value for m in at.markdown)
    assert "zfm-header" in textos  # cabecalho desenhado (a tela nao parou antes)
