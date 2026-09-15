"""Normalizacao, validacao e derivacao de CNPJ."""
from __future__ import annotations

import re

_PESOS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_LIMPEZA = re.compile(r"[^0-9A-Za-z]")


def normaliza(valor: str) -> str:
    """Remove pontuacao e espacos, devolve em maiusculas.

    Aceita caracteres alfanumericos por causa do CNPJ alfanumerico; para o
    CNPJ classico o resultado sao 14 digitos, que e o formato aceito pelo
    site da Receita.
    """
    return _LIMPEZA.sub("", str(valor or "")).upper()


def _valor(caractere: str) -> int:
    # Regra publicada para o CNPJ alfanumerico: valor = ord(c) - 48.
    # Para digitos ("0"-"9") isso devolve o proprio digito, entao a mesma
    # funcao atende o CNPJ classico.
    return ord(caractere) - 48


def _digito(valores: list[int], pesos: tuple[int, ...]) -> int:
    resto = sum(v * p for v, p in zip(valores, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def digitos_verificadores(base12: str) -> str:
    """Calcula os dois DVs a partir dos 12 primeiros caracteres."""
    base12 = normaliza(base12)
    if len(base12) != 12:
        raise ValueError("base do CNPJ deve ter 12 caracteres")
    valores = [_valor(c) for c in base12]
    d1 = _digito(valores, _PESOS_1)
    d2 = _digito(valores + [d1], _PESOS_2)
    return f"{d1}{d2}"


def valido(valor: str) -> bool:
    """True se o CNPJ tem 14 caracteres e DVs coerentes."""
    c = normaliza(valor)
    if len(c) != 14 or not c[12:].isdigit():
        return False
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", c):
        return False
    if len(set(c)) == 1:  # 00000000000000 e afins
        return False
    try:
        return digitos_verificadores(c[:12]) == c[12:]
    except ValueError:
        return False


def raiz(valor: str) -> str:
    """Os 8 primeiros caracteres: identificam a empresa, nao o estabelecimento."""
    return normaliza(valor)[:8]


def matriz_da_raiz(raiz_: str) -> str:
    """Monta o CNPJ da matriz (ordem 0001) a partir da raiz."""
    base = f"{normaliza(raiz_)[:8]}0001"
    return base + digitos_verificadores(base)


def formata(valor: str) -> str:
    """Devolve no formato 00.000.000/0000-00; se nao tiver 14, devolve limpo."""
    c = normaliza(valor)
    if len(c) != 14:
        return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
