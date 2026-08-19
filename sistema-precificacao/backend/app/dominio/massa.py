"""Balanco de massa do lote (secao 7.1).

Pesos sao grandezas distintas e nao intercambiaveis: bruto, tara, liquido,
aceito e vendavel. A equacao precisa fechar dentro da tolerancia configurada;
acima dela o lote nao pode ser encerrado sem aprovacao de excecao.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.dominio.excecoes import MassaInconsistenteError
from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir, percentual_br


@dataclass(frozen=True)
class BalancoMassa:
    """Resultado do balanco, com todas as grandezas separadas."""

    quantidade_bruta: Decimal
    quantidade_recusada: Decimal
    quantidade_aceita: Decimal
    quantidade_vendavel: Decimal
    quantidade_rejeito: Decimal
    perda_normal: Decimal
    perda_anormal: Decimal
    diferenca_nao_explicada: Decimal
    rendimento: Decimal
    taxa_rejeito: Decimal
    dentro_da_tolerancia: bool

    @property
    def perda_total(self) -> Decimal:
        return self.perda_normal + self.perda_anormal


def calcular_balanco(
    *,
    peso_bruto: Decimal,
    tara: Decimal,
    quantidade_recusada: Decimal = ZERO,
    quantidade_vendavel: Decimal,
    quantidade_rejeito: Decimal = ZERO,
    perda_normal: Decimal = ZERO,
    perda_anormal: Decimal = ZERO,
    tolerancia: Decimal = Decimal("0.02"),
    memoria: Memoria | None = None,
    bloquear_fora_da_tolerancia: bool = True,
) -> BalancoMassa:
    """Fecha o balanco de massa e calcula rendimento e taxa de rejeito.

    ``diferenca_nao_explicada`` e o que sobra depois de contabilizar produto,
    rejeito e perdas declaradas. Ela existe de proposito: some-la ao rendimento
    esconderia furto, erro de balanca ou apontamento faltante.
    """

    bruto = dec(peso_bruto) - dec(tara)
    aceita = bruto - dec(quantidade_recusada)
    vendavel = dec(quantidade_vendavel)
    rejeito = dec(quantidade_rejeito)
    normal = dec(perda_normal)
    anormal = dec(perda_anormal)

    saidas_declaradas = vendavel + rejeito + normal + anormal
    diferenca = aceita - saidas_declaradas

    rendimento = dividir(vendavel, aceita, "rendimento do lote")
    taxa_rejeito = dividir(rejeito, aceita, "taxa de rejeito")

    divergencia_relativa = abs(dividir(diferenca, aceita, "divergencia de massa"))
    dentro = divergencia_relativa <= dec(tolerancia)

    if memoria is not None:
        memoria.registrar(
            "Quantidade bruta",
            "Q_bruta = peso de entrada - tara",
            {"peso_bruto": peso_bruto, "tara": tara},
            bruto,
            "kg",
        )
        memoria.registrar(
            "Quantidade aceita",
            "Q_aceita = Q_bruta - quantidade recusada",
            {"Q_bruta": bruto, "recusada": quantidade_recusada},
            aceita,
            "kg",
        )
        memoria.registrar(
            "Rendimento",
            "Rendimento = Q_vendavel / Q_aceita",
            {"Q_vendavel": vendavel, "Q_aceita": aceita},
            rendimento,
            "fracao",
        )
        memoria.registrar(
            "Taxa de rejeito",
            "Taxa = Q_rejeito / Q_aceita",
            {"Q_rejeito": rejeito, "Q_aceita": aceita},
            taxa_rejeito,
            "fracao",
        )
        memoria.registrar(
            "Divergência de massa",
            "diferença = Q_aceita - (vendável + rejeito + perdas)",
            {
                "Q_aceita": aceita,
                "vendavel": vendavel,
                "rejeito": rejeito,
                "perda_normal": normal,
                "perda_anormal": anormal,
            },
            diferenca,
            "kg",
            alerta=(
                None
                if dentro
                else (
                    f"Divergência de {percentual_br(divergencia_relativa, 4)} "
                    f"acima da tolerância de {percentual_br(tolerancia, 4)}: "
                    f"encerramento do lote bloqueado."
                )
            ),
        )

    if not dentro and bloquear_fora_da_tolerancia:
        raise MassaInconsistenteError(
            f"Balanço de massa fora da tolerância: divergência de "
            f"{percentual_br(divergencia_relativa, 4)} contra limite de "
            f"{percentual_br(tolerancia, 4)}. O encerramento exige aprovação de "
            f"exceção com justificativa."
        )

    return BalancoMassa(
        quantidade_bruta=bruto,
        quantidade_recusada=dec(quantidade_recusada),
        quantidade_aceita=aceita,
        quantidade_vendavel=vendavel,
        quantidade_rejeito=rejeito,
        perda_normal=normal,
        perda_anormal=anormal,
        diferenca_nao_explicada=diferenca,
        rendimento=rendimento,
        taxa_rejeito=taxa_rejeito,
        dentro_da_tolerancia=dentro,
    )
