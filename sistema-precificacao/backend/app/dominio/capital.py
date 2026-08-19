"""Capital de giro e provisoes de risco (secao 6.8).

Pagar o fornecedor antes de receber do cliente consome capital, e esse consumo
tem preco. O custo financeiro cresce com o prazo -- e por isso que uma cotacao
com prazo maior precisa apresentar custo maior (caso de teste 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.memoria import Memoria
from app.dominio.unidades import UM, ZERO, dec, taxa_diaria_equivalente


@dataclass(frozen=True)
class CicloFinanceiro:
    dias_estoque: int
    dias_recebimento: int
    dias_pagamento: int

    @property
    def dias_comprometidos(self) -> int:
        """Dias em que o capital fica fora do caixa da empresa."""

        return self.dias_estoque + self.dias_recebimento - self.dias_pagamento


@dataclass(frozen=True)
class CustoCapital:
    capital_comprometido: Decimal
    dias_comprometidos: int
    taxa_diaria: Decimal
    custo_financeiro: Decimal


def calcular_custo_capital(
    *,
    capital_comprometido: Decimal,
    ciclo: CicloFinanceiro,
    taxa_anual: Decimal,
    memoria: Memoria | None = None,
) -> CustoCapital:
    """Custo financeiro do lote por capitalizacao composta.

    Ciclo negativo (recebe antes de pagar) nao gera custo: gera folga de caixa,
    tratada como zero aqui para nao criar receita financeira ficticia no custo.
    """

    dias = ciclo.dias_comprometidos
    taxa_dia = taxa_diaria_equivalente(taxa_anual)
    capital = dec(capital_comprometido)

    if dias <= 0:
        custo = ZERO
    else:
        custo = capital * ((UM + taxa_dia) ** Decimal(dias) - UM)

    if memoria is not None:
        memoria.registrar(
            "Dias do ciclo financeiro",
            "dias = dias de estoque + dias de recebimento - dias de pagamento",
            {
                "dias_estoque": ciclo.dias_estoque,
                "dias_recebimento": ciclo.dias_recebimento,
                "dias_pagamento": ciclo.dias_pagamento,
            },
            Decimal(dias),
            "dias",
        )
        memoria.registrar(
            "Custo financeiro do lote",
            "custo = capital comprometido × [(1 + taxa diaria) ^ dias - 1]",
            {
                "capital_comprometido": capital,
                "taxa_diaria": taxa_dia,
                "dias": dias,
            },
            custo,
            "BRL",
            alerta=(
                "Ciclo financeiro nao positivo: nenhum custo de capital atribuido."
                if dias <= 0
                else None
            ),
        )

    return CustoCapital(
        capital_comprometido=capital,
        dias_comprometidos=dias,
        taxa_diaria=taxa_dia,
        custo_financeiro=custo,
    )


@dataclass
class ProvisaoRisco:
    """Provisao com base historica declarada.

    A secao 6.8 proibe somar um percentual generico de 'imprevistos': cada
    provisao precisa de origem identificada.
    """

    nome: str
    percentual: Decimal
    base: Decimal
    origem_historica: str

    @property
    def valor(self) -> Decimal:
        return dec(self.percentual) * dec(self.base)


@dataclass(frozen=True)
class ResultadoProvisoes:
    total: Decimal
    detalhamento: dict[str, Decimal] = field(default_factory=dict)


def calcular_provisoes(
    provisoes: list[ProvisaoRisco],
    *,
    memoria: Memoria | None = None,
) -> ResultadoProvisoes:
    detalhamento = {p.nome: p.valor for p in provisoes}
    total = sum(detalhamento.values(), ZERO)

    if memoria is not None and provisoes:
        for provisao in provisoes:
            memoria.registrar(
                f"Provisao de risco: {provisao.nome}",
                "valor = percentual historico × base",
                {
                    "percentual": provisao.percentual,
                    "base": provisao.base,
                    "origem": provisao.origem_historica,
                },
                provisao.valor,
                "BRL",
                fonte=provisao.origem_historica,
            )

    return ResultadoProvisoes(total=total, detalhamento=detalhamento)
