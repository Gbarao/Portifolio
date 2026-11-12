# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller para gerar o executável (pasta ConsolidadorEFD/).
# Uso:  pyinstaller --noconfirm empacotar/consolidador_efd.spec

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))

datas, binaries, hiddenimports = [], [], []
for pacote in ("streamlit", "duckdb", "pyarrow", "altair"):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h
for pacote in ("streamlit", "duckdb", "pandas", "pyarrow", "altair", "xlsxwriter", "openpyxl"):
    datas += copy_metadata(pacote)
# Os módulos do programa são listados pelos arquivos da pasta efd/ (a coleta
# automática depende de onde o comando é chamado e pode voltar vazia).
MODULOS_EFD = ["efd"] + sorted(
    "efd." + os.path.splitext(n)[0] for n in os.listdir(os.path.join(RAIZ, "efd"))
    if n.endswith(".py") and n != "__init__.py")
for obrigatorio in ("efd.base", "efd.comparacao", "efd.consulta", "efd.leiautes", "efd.leitor",
                    "efd.seletor", "efd.trabalhador"):
    if obrigatorio not in MODULOS_EFD:
        raise SystemExit(f"Módulo do programa não encontrado para empacotar: {obrigatorio}")
hiddenimports += MODULOS_EFD
hiddenimports += ["pandas", "xlsxwriter", "openpyxl", "tkinter", "tkinter.filedialog"]
datas += [(os.path.join(RAIZ, "app.py"), ".")]

a = Analysis(
    [os.path.join(RAIZ, "consolidador_efd.py")],
    pathex=[RAIZ],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "IPython", "pytest", "cryptography"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ConsolidadorEFD",
          console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="ConsolidadorEFD")
