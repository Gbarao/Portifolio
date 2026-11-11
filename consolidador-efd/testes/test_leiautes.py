#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere o leiaute usado pelo programa (efd/leiautes.py e as posições lidas em
efd/leitor.py) contra os campos extraídos dos Guias Práticos oficiais
(testes/leiautes_guias_praticos.json)."""

import ast
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from efd.leiautes import CONTRIB, FISCAL, NOMES_CAMPOS  # noqa: E402


def bate(a, b):
    a, b = a.replace("-", ""), b.replace("-", "")
    return a == b or a.startswith(b) or b.startswith(a)


def main():
    guia = json.load(open(os.path.join(AQUI, "leiautes_guias_praticos.json"), encoding="utf-8"))
    falhas, total = [], 0
    for fonte in (FISCAL, CONTRIB):
        for reg, nomes_guia in guia[fonte].items():
            nomes = NOMES_CAMPOS[fonte][reg]
            for i, g in enumerate(nomes_guia):
                total += 1
                if i >= len(nomes) or not bate(nomes[i], g):
                    falhas.append(f"{fonte} {reg} campo {i + 1}: programa={nomes[i] if i < len(nomes) else '-'} guia={g}")
    # posições anotadas nas funções de leitura
    arvore = ast.parse(open(os.path.join(AQUI, "..", "efd", "leitor.py"), encoding="utf-8").read())
    posicoes = 0
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        doc = (ast.get_docstring(no) or "").replace("\n", "")
        if not re.match(r"\|[0-9A-Z]{4}", doc):
            continue
        regs = re.findall(r"[0-9A-Z]{4}", doc.split("|")[1])
        fontes = [FISCAL] if no.name.startswith("f_") or "(EFD Fiscal)" in doc else \
            [CONTRIB] if no.name.startswith("c_") or "Contribuições" in doc else [FISCAL, CONTRIB]
        for campo, pos in re.findall(r"([A-Z][A-Z0-9_\-]*)\[(\d+)\]", doc):
            for reg in regs:
                for f in fontes:
                    g = guia[f].get(reg)
                    if not g or reg in ("C191", "C195"):
                        continue
                    posicoes += 1
                    if int(pos) > len(g) or not bate(campo, g[int(pos) - 1]):
                        falhas.append(f"{no.name}: {reg} posição {pos} lida como {campo}, guia diz "
                                      f"{g[int(pos) - 1] if int(pos) <= len(g) else '-'}")
    print(f"{total} campos e {posicoes} posições de leitura conferidos contra os Guias Práticos.")
    for f in falhas:
        print("FALHA:", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
