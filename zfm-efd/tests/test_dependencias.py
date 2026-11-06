"""Falha se o codigo importar pacote fora do requirements.txt (SPEC 9)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# nome do pacote no pip -> nome do modulo importado
MODULOS = {"duckdb": "duckdb", "streamlit": "streamlit", "plotly": "plotly", "pandas": "pandas",
           "openpyxl": "openpyxl", "pytest": "pytest"}
LOCAIS = {"zfm", "tests", "iniciar"}


def _permitidos() -> set[str]:
    nomes = set()
    for l in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines():
        l = l.split("#")[0].strip()
        if l:
            nomes.add(MODULOS.get(l.split("==")[0].strip().lower(), l.split("==")[0].strip()))
    return nomes | set(sys.stdlib_module_names) | LOCAIS | {"__future__"}


def _imports(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    mods = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            mods |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            mods.add(no.module.split(".")[0])
    return mods


def test_somente_pacotes_do_requirements():
    permitidos = _permitidos()
    fora = {}
    for arq in RAIZ.rglob("*.py"):
        if ".venv" in arq.parts or "data" in arq.parts:
            continue
        extras = _imports(arq) - permitidos
        if extras:
            fora[str(arq.relative_to(RAIZ))] = sorted(extras)
    assert not fora, f"Pacotes fora do requirements.txt: {fora}"


def test_ferramentas_usam_so_biblioteca_padrao():
    # iniciar/diagnostico rodam ANTES de os pacotes existirem
    permitidos = set(sys.stdlib_module_names) | {"__future__", "iniciar"}
    for nome in ("iniciar.py", "diagnostico.py", "testar.py"):
        extras = _imports(RAIZ / "ferramentas" / nome) - permitidos
        assert not extras, f"{nome} importa {extras}"


def test_sem_recursos_de_rede_nas_telas():
    # Nenhuma tela ou modulo carrega recurso remoto (fontes, scripts, imagens, APIs)
    proibidos = ("http://", "https://", "requests", "urllib.request")
    for arq in list((RAIZ / "zfm").rglob("*.py")) + list((RAIZ / "pages").glob("*.py")) + [RAIZ / "app.py"]:
        txt = arq.read_text(encoding="utf-8")
        for p in proibidos:
            assert p not in txt, f"{arq.name} contem {p}"


def test_streamlit_so_local_e_sem_telemetria():
    cfg = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'address = "127.0.0.1"' in cfg
    assert "gatherUsageStats = false" in cfg
