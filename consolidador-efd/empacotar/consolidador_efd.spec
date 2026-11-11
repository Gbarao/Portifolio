# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller para gerar o executável (pasta ConsolidadorEFD/).
# Uso:  pyinstaller --noconfirm empacotar/consolidador_efd.spec

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))

datas, binaries, hiddenimports = [], [], []
for pacote in ("streamlit", "duckdb", "pyarrow", "altair"):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h
for pacote in ("streamlit", "duckdb", "pandas", "pyarrow", "altair", "xlsxwriter", "openpyxl"):
    datas += copy_metadata(pacote)
hiddenimports += collect_submodules("efd")
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
