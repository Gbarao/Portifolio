"""Reconciliacao entre resultado por lote e resultado do periodo (secao 13.3).

A soma dos resultados por lote precisa bater com o resultado mensal dentro da
tolerancia aprovada. Divergencia acima disso nao e arredondamento: e custo
lancado no periodo sem lote, lote sem apontamento ou taxa desatualizada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir, percentual_br


@dataclass(frozen=True)
class ResultadoLote:
    codigo: str
    receita: Decimal
    custo_total: Decimal

    @property
    def resultado(self) -> Decimal:
        return dec(self.receita) - dec(self.custo_total)


@dataclass(frozen=True)
class Reconciliacao:
    soma_dos_lotes: Decimal
    resultado_do_periodo: Decimal
    itens_nao_atribuidos: dict[str, Decimal]
    divergencia: Decimal
    divergencia_relativa: Decimal
    dentro_da_tolerancia: bool
    alertas: list[str] = field(default_factory=list)


def reconciliar_periodo(
    lotes: list[ResultadoLote],
    *,
    resultado_do_periodo: Decimal,
    custo_ociosidade: Decimal = ZERO,
    perdas_anormais: Decimal = ZERO,
    outros_itens_do_periodo: dict[str, Decimal] | None = None,
    tolerancia: Decimal = Decimal("0.01"),
    memoria: Memoria | None = None,
) -> Reconciliacao:
    """Confronta a soma dos lotes com o resultado contabil do periodo.

    Ociosidade e perda anormal sao subtraidas explicitamente porque nao
    pertencem a lote nenhum -- se fossem rateadas nos lotes, a reconciliacao
    fecharia escondendo justamente o que a gestao precisa enxergar.
    """

    outros = dict(outros_itens_do_periodo or {})
    if dec(custo_ociosidade) != ZERO:
        outros["custo_ociosidade"] = dec(custo_ociosidade)
    if dec(perdas_anormais) != ZERO:
        outros["perdas_anormais"] = dec(perdas_anormais)

    soma_lotes = sum((lote.resultado for lote in lotes), ZERO)
    total_nao_atribuido = sum(outros.values(), ZERO)
    esperado = soma_lotes - total_nao_atribuido
    divergencia = dec(resultado_do_periodo) - esperado

    base = abs(dec(resultado_do_periodo)) or abs(esperado)
    relativa = (
        abs(dividir(divergencia, base, "divergencia relativa")) if base != ZERO else ZERO
    )
    dentro = relativa <= dec(tolerancia)

    alertas: list[str] = []
    if not dentro:
        alertas.append(
            f"Divergência de {percentual_br(relativa, 4)} entre a soma dos lotes "
            f"e o resultado do período, acima da tolerância de "
            f"{percentual_br(tolerancia, 4)}. Revise custos lançados sem lote e "
            f"lotes sem apontamento antes de fechar o mês."
        )

    if memoria is not None:
        memoria.registrar(
            "Reconciliação do período",
            "divergência = resultado do período - (Σ resultados por lote "
            "- itens não atribuíveis a lote)",
            {
                "soma_dos_lotes": soma_lotes,
                "itens_nao_atribuidos": total_nao_atribuido,
                "resultado_do_periodo": resultado_do_periodo,
            },
            divergencia,
            "BRL",
            alerta=alertas[0] if alertas else None,
        )

    return Reconciliacao(
        soma_dos_lotes=soma_lotes,
        resultado_do_periodo=dec(resultado_do_periodo),
        itens_nao_atribuidos=outros,
        divergencia=divergencia,
        divergencia_relativa=relativa,
        dentro_da_tolerancia=dentro,
        alertas=alertas,
    )
