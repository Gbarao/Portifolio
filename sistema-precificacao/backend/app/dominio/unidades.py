"""Normalizacao de unidades, aritmetica decimal e guardas de calculo.

Convencoes internas, validas em todo o motor:

* peso em quilogramas, distancia em quilometros, tempo em horas, valor em BRL;
* percentuais sao fracoes decimais -- 9,25% e ``Decimal("0.0925")``;
* nenhum arredondamento intermediario: arredonda-se apenas na apresentacao,
  com as casas definidas em ``empresa_parametro``.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Any

from app.dominio.excecoes import DenominadorZeroError

# 28 digitos significativos cobrem com folga a cadeia
# preco -> lote -> rateio -> preco unitario sem erro acumulado perceptivel.
PRECISAO_INTERNA = 28

ZERO = Decimal("0")
UM = Decimal("1")
CEM = Decimal("100")
KG_POR_TONELADA = Decimal("1000")


def dec(valor: Any) -> Decimal:
    """Converte para Decimal sem passar por float.

    ``Decimal(0.1)`` carrega o erro binario do float; ``Decimal("0.1")`` nao.
    Por isso numeros vindos de fora sao convertidos via ``str``.
    """

    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, float):
        return Decimal(str(valor))
    return Decimal(valor)


def dividir(numerador: Any, denominador: Any, contexto: str = "calculo") -> Decimal:
    """Divisao com bloqueio explicito de denominador zero.

    Rendimento, taxa de atividade e custo unitario dividem por quantidades que
    podem ser zero em lote vazio ou recurso sem capacidade cadastrada. Deixar
    estourar ``DivisionByZero`` esconderia a causa real do usuario.
    """

    n, d = dec(numerador), dec(denominador)
    if d == ZERO:
        raise DenominadorZeroError(
            f"Denominador zero em {contexto}: verifique quantidade ou capacidade."
        )
    with localcontext() as ctx:
        ctx.prec = PRECISAO_INTERNA
        return n / d


def arredondar(valor: Any, casas: int = 4, modo: str = ROUND_HALF_UP) -> Decimal:
    """Arredonda para apresentacao. Nao usar em passos intermediarios."""

    expoente = Decimal(1).scaleb(-casas)
    return dec(valor).quantize(expoente, rounding=modo)


def kg_para_toneladas(kg: Any) -> Decimal:
    return dividir(kg, KG_POR_TONELADA, "conversao kg -> t")


def toneladas_para_kg(toneladas: Any) -> Decimal:
    return dec(toneladas) * KG_POR_TONELADA


def percentual(fracao: Any, casas: int = 4) -> Decimal:
    """Converte fracao decimal para percentual legivel (0.0925 -> 9.2500)."""

    return arredondar(dec(fracao) * CEM, casas)


def taxa_diaria_equivalente(taxa_anual: Any, dias_ano: int = 365) -> Decimal:
    """Converte taxa anual em diaria equivalente por capitalizacao composta.

    Dividir a taxa anual por 365 subestimaria o custo do capital; a secao 6.8
    trabalha com capitalizacao, nao com juros simples.
    """

    with localcontext() as ctx:
        ctx.prec = PRECISAO_INTERNA
        return (UM + dec(taxa_anual)) ** (UM / Decimal(dias_ano)) - UM
