"""Camadas de custo e as tres visoes reconciliaveis (secoes 2, 7.5 e 8).

Cada componente de custo declara a partir de qual camada ele passa a contar.
As camadas sao cumulativas: caixa ⊂ contribuicao ⊂ operacional ⊂ sustentavel.
Isso impede o erro classico de comparar preco de uma camada com custo de outra.

As tres visoes convivem sem se misturar:

* **contabil** -- custo de estoque pela politica aprovada; nao recebe despesa
  administrativa nem custo de capital;
* **gerencial completo** -- tudo que a operacao precisa para se sustentar;
* **relevante** -- apenas o que muda em razao da decisao analisada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir

CAMADA_CAIXA = "CAIXA"
CAMADA_CONTRIBUICAO = "CONTRIBUICAO"
CAMADA_OPERACIONAL = "OPERACIONAL"
CAMADA_SUSTENTAVEL = "SUSTENTAVEL"

# Ordem cumulativa das camadas.
ORDEM_CAMADAS = [
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
]

VISAO_CONTABIL = "CONTABIL"
VISAO_GERENCIAL = "GERENCIAL_COMPLETO"
VISAO_RELEVANTE = "RELEVANTE"


@dataclass
class ComponenteCusto:
    """Um componente do custo do lote.

    ``camada_minima`` diz a partir de qual degrau ele entra; ``visoes`` diz em
    quais das tres visoes ele aparece. Um mesmo numero nunca e cadastrado duas
    vezes -- e essa unicidade que evita a dupla contagem da regra 12.
    """

    nome: str
    valor: Decimal
    camada_minima: str
    visoes: tuple[str, ...] = (VISAO_CONTABIL, VISAO_GERENCIAL)
    # Desembolso incremental inevitavel: entra no preco de caixa.
    e_desembolso: bool = True
    # Custo que muda em razao da decisao analisada.
    e_relevante_para_decisao: bool = True


@dataclass(frozen=True)
class CustoPorCamada:
    total: Decimal
    unitario: Decimal
    componentes: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class EstruturaCustos:
    """Custos totais e unitarios em cada camada e visao."""

    quantidade_vendavel: Decimal
    camadas: dict[str, CustoPorCamada]
    visoes: dict[str, Decimal]

    def unitario(self, camada: str) -> Decimal:
        return self.camadas[camada].unitario

    def total(self, camada: str) -> Decimal:
        return self.camadas[camada].total


def montar_estrutura(
    componentes: list[ComponenteCusto],
    *,
    quantidade_vendavel: Decimal,
    memoria: Memoria | None = None,
) -> EstruturaCustos:
    """Consolida os componentes nas quatro camadas e nas tres visoes."""

    indice_camada = {nome: i for i, nome in enumerate(ORDEM_CAMADAS)}
    camadas: dict[str, CustoPorCamada] = {}

    for camada in ORDEM_CAMADAS:
        limite = indice_camada[camada]
        incluidos = {
            c.nome: dec(c.valor)
            for c in componentes
            if indice_camada[c.camada_minima] <= limite
            # O preco de caixa considera apenas desembolso incremental:
            # depreciacao e provisao nao saem do caixa hoje.
            and (camada != CAMADA_CAIXA or c.e_desembolso)
        }
        total = sum(incluidos.values(), ZERO)
        camadas[camada] = CustoPorCamada(
            total=total,
            unitario=dividir(
                total, quantidade_vendavel, f"custo unitario da camada {camada}"
            ),
            componentes=incluidos,
        )

    visoes = {
        VISAO_CONTABIL: sum(
            (dec(c.valor) for c in componentes if VISAO_CONTABIL in c.visoes), ZERO
        ),
        VISAO_GERENCIAL: sum(
            (dec(c.valor) for c in componentes if VISAO_GERENCIAL in c.visoes), ZERO
        ),
        VISAO_RELEVANTE: sum(
            (dec(c.valor) for c in componentes if c.e_relevante_para_decisao), ZERO
        ),
    }

    if memoria is not None:
        for camada in ORDEM_CAMADAS:
            memoria.registrar(
                f"Custo total da camada {camada}",
                "soma dos componentes cuja camada minima ja foi alcancada",
                camadas[camada].componentes,
                camadas[camada].total,
                "BRL",
            )
            memoria.registrar(
                f"Custo unitario da camada {camada}",
                "custo total da camada / quantidade vendavel",
                {
                    "custo_total": camadas[camada].total,
                    "Q_vendavel": quantidade_vendavel,
                },
                camadas[camada].unitario,
                "BRL/kg",
            )
        memoria.registrar(
            "Custo contabil do estoque",
            "componentes elegiveis a valorizacao de estoque",
            {"componentes": len([c for c in componentes if VISAO_CONTABIL in c.visoes])},
            visoes[VISAO_CONTABIL],
            "BRL",
        )

    return EstruturaCustos(
        quantidade_vendavel=dec(quantidade_vendavel),
        camadas=camadas,
        visoes=visoes,
    )
