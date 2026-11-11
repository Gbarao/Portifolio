# -*- coding: utf-8 -*-
"""
Comparação campo a campo de um mesmo documento em dois lados (EFD
Contribuições x EFD Fiscal, ou duas ocorrências do mesmo documento).

Cada lado é a lista de linhas originais do TXT do documento: o cabeçalho
(C100, C500, D100, D500, A100) e os registros filhos. A comparação usa os
NOMES dos campos de cada leiaute, então campos com o mesmo nome nas duas
escriturações (NUM_DOC, VL_DOC, CFOP, VL_ICMS...) são comparados mesmo que
estejam em posições diferentes.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .leiautes import campos_da_linha

# Chave que casa os registros filhos entre os dois lados
CHAVE_FILHO = {"C170": "NUM_ITEM", "A170": "NUM_ITEM", "D101": "IND_NAT_FRT",
               "D105": "IND_NAT_FRT"}
CABECALHOS = {"C100", "C500", "D100", "D500", "A100", "F100"}


def _numero(v: str):
    t = (v or "").strip()
    if t == "":
        return Decimal(0)
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def iguais(a: str, b: str) -> bool:
    """Igualdade de conteúdo: números pelo valor (1000,00 = 1000,0; vazio = 0),
    texto sem espaços nas pontas e sem zeros à esquerda em códigos numéricos."""
    a, b = (a or "").strip(), (b or "").strip()
    if a == b:
        return True
    na, nb = _numero(a), _numero(b)
    if na is not None and nb is not None and ("," in a or "," in b or a == "" or b == ""):
        return na == nb
    if a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return False


IGUAL, DIFERENTE, UM_LADO = "Igual", "Diferente", "Informado só de um lado"
CODIGO = "Código interno de cada EFD"
# Códigos que cada escrituração define no próprio Bloco 0: podem ser diferentes
# nas duas EFDs para o mesmo participante/item sem que isso seja erro.
CODIGOS_INTERNOS = frozenset(("COD_PART", "COD_ITEM", "COD_NAT"))


def situacao(a: str, b: str) -> str:
    a, b = (a or "").strip(), (b or "").strip()
    if iguais(a, b):
        return IGUAL
    if a == "" or b == "":
        return UM_LADO
    return DIFERENTE


def _por_registro(fonte, linhas):
    """{registro: [(linha, {campo: valor}, [(campo, valor)])]} na ordem do arquivo."""
    grupos = {}
    for linha, registro, texto in linhas:
        pares = campos_da_linha(fonte, texto)
        grupos.setdefault(registro, []).append((linha, dict(pares), pares))
    return grupos


def _parear(reg, a_lista, b_lista):
    chave = CHAVE_FILHO.get(reg)
    if chave:
        mapa_b = {}
        for x in b_lista:
            mapa_b.setdefault(x[1].get(chave, "").lstrip("0"), []).append(x)
        pares, usados = [], set()
        for x in a_lista:
            k = x[1].get(chave, "").lstrip("0")
            candidatos = [y for y in mapa_b.get(k, []) if id(y) not in usados]
            y = candidatos[0] if candidatos else None
            if y is not None:
                usados.add(id(y))
            pares.append((f"{chave} {k}", x, y))
        for lista in mapa_b.values():
            for y in lista:
                if id(y) not in usados:
                    pares.append((f"{chave} {y[1].get(chave, '')}", None, y))
        return pares
    n = max(len(a_lista), len(b_lista))
    return [(f"{i + 1}º" if n > 1 else "", a_lista[i] if i < len(a_lista) else None,
             b_lista[i] if i < len(b_lista) else None) for i in range(n)]


def comparar(lado_a: dict, lado_b: dict):
    """Compara dois lados. lado = {"fonte": FISCAL|CONTRIB, "linhas": [(linha, reg, texto)]}.

    Devolve (linhas_da_comparacao, linhas_divergentes_a, linhas_divergentes_b), em que
    cada linha da comparação é um dict com registro, referencia, campo, valor_a,
    valor_b, linha_a, linha_b e situacao (Igual, Diferente ou Informado só de um
    lado). As linhas divergentes são as que têm ao menos um campo Diferente.
    """
    entre_efds = lado_a["fonte"] != lado_b["fonte"]
    ga = _por_registro(lado_a["fonte"], lado_a["linhas"])
    gb = _por_registro(lado_b["fonte"], lado_b["linhas"])
    saida, div_a, div_b = [], set(), set()

    # cabeçalhos podem ter registros diferentes (ex.: C500 x C500 de leiautes distintos)
    cab_a = next((r for r in ga if r in CABECALHOS), None)
    cab_b = next((r for r in gb if r in CABECALHOS), None)
    blocos = []
    if cab_a and cab_b:
        blocos.append((cab_a if cab_a == cab_b else f"{cab_a} × {cab_b}",
                       [("", ga[cab_a][0], gb[cab_b][0])]))
    for reg in [r for r in ga if r in gb and r not in CABECALHOS]:
        blocos.append((reg, _parear(reg, ga[reg], gb[reg])))

    for reg, pares in blocos:
        for ref, x, y in pares:
            if x is None or y is None:
                presente = x or y
                saida.append({"registro": reg, "referencia": ref, "campo": "(registro inteiro)",
                              "valor_a": "presente" if x else "ausente",
                              "valor_b": "presente" if y else "ausente",
                              "linha_a": x[0] if x else None, "linha_b": y[0] if y else None,
                              "situacao": DIFERENTE})
                (div_a if x else div_b).add(presente[0])
                continue
            nomes_b = y[1]
            for campo, va in x[2]:
                if campo == "REG" or campo.startswith("CAMPO_") or campo not in nomes_b:
                    continue
                vb = nomes_b[campo]
                sit = situacao(va, vb)
                if sit != IGUAL and entre_efds and campo in CODIGOS_INTERNOS:
                    sit = CODIGO
                saida.append({"registro": reg, "referencia": ref, "campo": campo,
                              "valor_a": va, "valor_b": vb, "linha_a": x[0], "linha_b": y[0],
                              "situacao": sit})
                if sit == DIFERENTE:
                    div_a.add(x[0])
                    div_b.add(y[0])
    return saida, div_a, div_b
