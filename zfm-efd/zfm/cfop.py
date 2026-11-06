"""Classificacao automatica de CFOP (editavel em param_cfops).

Regras pelos 3 ultimos digitos da tabela de CFOP (Convenio s/n de 1970, Ajuste
SINIEF 07/01). Primeiro digito: 1/2/3 entrada (estadual/interestadual/exterior);
5/6/7 saida (estadual/interestadual/exterior).
"""
from __future__ import annotations

_VENDA_PROD = {"101", "103", "105", "107", "109", "111", "113", "116", "118", "122", "124",
               "125", "401", "402"}
_VENDA_REV = {"102", "104", "106", "108", "110", "112", "114", "115", "117", "119", "120",
              "123", "403", "404", "405"}
_TRANSF = {"151", "152", "153", "154", "155", "156", "408", "409", "552", "557"}
_DEVOL_SAIDA = {"201", "202", "203", "204", "205", "206", "207", "208", "209", "210", "211",
                "212", "410", "411", "412", "413", "503", "553", "555", "556", "660", "661", "662"}
_DEVOL_ENTRADA = {"201", "202", "203", "204", "205", "206", "207", "208", "209", "210", "211",
                  "212", "410", "411", "503", "553", "660", "661", "662"}
_COMPRA_IND = {"101", "111", "116", "118", "120", "122", "126", "127", "128", "401"}
_COMPRA_REV = {"102", "113", "117", "121", "403"}
_ATIVO = {"406", "551"}
_USO = {"407", "556"}

CATEGORIAS = ["venda_producao", "venda_revenda", "servico", "transferencia", "devolucao",
              "remessa_retorno", "ativo_uso", "compra_industrializacao", "compra_revenda",
              "ativo", "uso_consumo", "insumo_servico", "outros"]

# Categorias de entrada que gerariam credito no regime nao cumulativo de CBS/IBS
CATEGORIAS_CREDITAVEIS = ("compra_industrializacao", "compra_revenda", "ativo", "uso_consumo",
                          "insumo_servico")


def sentido(cfop: str) -> str:
    return "entrada" if str(cfop)[:1] in "123" else "saida"


def classificar(cfop: str) -> tuple[str, bool]:
    """Retorna (categoria, eh_receita)."""
    c = str(cfop or "").strip()
    if len(c) != 4 or not c.isdigit():
        return "outros", False
    d, s = c[0], c[1:]
    if d in "567":
        if s in _VENDA_PROD:
            return "venda_producao", True
        if s in _VENDA_REV:
            return "venda_revenda", True
        if s in ("933", "932", "301", "302", "303", "304", "305", "306", "307", "351", "352",
                 "353", "354", "355", "356", "357", "359", "360"):
            return "servico", True
        if s in _TRANSF:
            return "transferencia", False
        if s in _DEVOL_SAIDA:
            return "devolucao", False
        if s == "551":
            return "ativo_uso", False
        if s[0] == "9" or s in ("501", "502", "504", "505"):
            return "remessa_retorno", False
        return "outros", False
    # entradas
    if s in _COMPRA_IND:
        return "compra_industrializacao", False
    if s in _COMPRA_REV:
        return "compra_revenda", False
    if s in _ATIVO:
        return "ativo", False
    if s in _USO:
        return "uso_consumo", False
    if s in _TRANSF:
        return "transferencia", False
    if s in _DEVOL_ENTRADA:
        return "devolucao", False
    if s[:2] in ("25", "30", "35") or s in ("933", "932"):
        return "insumo_servico", False  # energia, comunicacao, transporte, servicos
    if s[0] == "9" or s in ("501", "502", "504", "505"):
        return "remessa_retorno", False
    return "outros", False
