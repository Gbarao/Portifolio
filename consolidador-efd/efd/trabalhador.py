# -*- coding: utf-8 -*-
"""
Processo de leitura de UM arquivo:  python -m efd.trabalhador <pasta>

A pasta contém `info.json` (resultado da inspeção do arquivo). O processo lê a
escrituração, grava os Parquet na mesma pasta e, por último, `meta.json` com
os totais de controle. É um processo independente (não usa multiprocessing),
para funcionar igual no Windows, no Linux e dentro da interface.
"""

import json
import os
import sys

from .leitor import processar_arquivo


def main() -> int:
    pasta = sys.argv[1]
    with open(os.path.join(pasta, "info.json"), "r", encoding="utf-8") as f:
        info = json.load(f)
    meta = processar_arquivo(info, pasta)
    provisorio = os.path.join(pasta, "meta.json.tmp")
    with open(provisorio, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    os.replace(provisorio, os.path.join(pasta, "meta.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
