"""Produtos conjuntos e subprodutos (secao 7.4).

Quando a triagem gera varios produtos e o custo nao pode ser medido
diretamente, o criterio preferencial e o valor realizavel liquido relativo.
O rateio precisa fechar 100% do custo conjunto -- o residuo de arredondamento
vai para o produto de maior VRL, nunca desaparece.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.dominio.excecoes import ParametroInvalidoError
from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir


@dataclass(frozen=True)
class ProdutoConjunto:
    codigo: str
    quantidade: Decimal
    preco_estimado_venda: Decimal
    gastos_posteriores: Decimal = ZERO
    e_subproduto: bool = False

    @property
    def valor_realizavel_liquido(self) -> Decimal:
        return dec(self.quantidade) * (
            dec(self.preco_estimado_venda) - dec(self.gastos_posteriores)
        )


@dataclass(frozen=True)
class RateioProduto:
    codigo: str
    valor_realizavel_liquido: Decimal
    fator: Decimal
    custo_atribuido: Decimal


def ratear_por_vrl(
    custo_conjunto: Decimal,
    produtos: list[ProdutoConjunto],
    *,
    memoria: Memoria | None = None,
    casas_residuo: int = 6,
) -> list[RateioProduto]:
    """Distribui o custo conjunto pelo valor realizavel liquido relativo."""

    if not produtos:
        raise ParametroInvalidoError("Rateio exige ao menos um produto de saida.")

    vrls = {p.codigo: p.valor_realizavel_liquido for p in produtos}
    soma_vrl = sum(vrls.values(), ZERO)

    if soma_vrl <= ZERO:
        raise ParametroInvalidoError(
            "Soma dos valores realizaveis liquidos e zero ou negativa: "
            "revise precos estimados e gastos posteriores antes de ratear."
        )

    custo = dec(custo_conjunto)
    rateios: list[RateioProduto] = []
    acumulado = ZERO

    # O ultimo produto (maior VRL) absorve o residuo, garantindo que a soma
    # dos custos atribuidos seja exatamente o custo conjunto (caso de teste 2).
    ordenados = sorted(produtos, key=lambda p: vrls[p.codigo], reverse=True)
    for produto in ordenados[1:]:
        fator = dividir(vrls[produto.codigo], soma_vrl, "fator de rateio")
        atribuido = (custo * fator).quantize(Decimal(1).scaleb(-casas_residuo))
        acumulado += atribuido
        rateios.append(
            RateioProduto(
                codigo=produto.codigo,
                valor_realizavel_liquido=vrls[produto.codigo],
                fator=fator,
                custo_atribuido=atribuido,
            )
        )

    principal = ordenados[0]
    fator_principal = dividir(vrls[principal.codigo], soma_vrl, "fator de rateio")
    rateios.insert(
        0,
        RateioProduto(
            codigo=principal.codigo,
            valor_realizavel_liquido=vrls[principal.codigo],
            fator=fator_principal,
            custo_atribuido=custo - acumulado,
        ),
    )

    if memoria is not None:
        for rateio in rateios:
            memoria.registrar(
                f"Rateio do custo conjunto para {rateio.codigo}",
                "VRL_i = quantidade × (preco estimado - gastos posteriores); "
                "fator_i = VRL_i / Σ VRL; custo_i = custo conjunto × fator_i",
                {
                    "VRL_i": rateio.valor_realizavel_liquido,
                    "soma_VRL": soma_vrl,
                    "fator": rateio.fator,
                    "custo_conjunto": custo,
                },
                rateio.custo_atribuido,
                "BRL",
            )

    return rateios


def creditar_subproduto(
    custo_conjunto: Decimal,
    receita_liquida_subproduto: Decimal,
    *,
    politica_aprovada: bool,
    memoria: Memoria | None = None,
) -> Decimal:
    """Reduz o custo conjunto pela receita do subproduto -- se autorizado.

    A secao 7.4 condiciona esse tratamento a politica contabil e gerencial
    formalmente aprovada. Sem aprovacao, o custo permanece integral e a
    receita e reconhecida como receita (regra 13 da secao 11: os dois
    tratamentos nunca coexistem para o mesmo valor).
    """

    if not politica_aprovada:
        if memoria is not None:
            memoria.registrar(
                "Receita de subproduto",
                "mantida como receita; custo conjunto nao reduzido",
                {"receita_liquida": receita_liquida_subproduto},
                dec(custo_conjunto),
                "BRL",
                status_dado="CONFIRMADO",
                alerta=(
                    "Politica de credito de subproduto nao aprovada: a receita nao "
                    "reduziu o custo conjunto."
                ),
            )
        return dec(custo_conjunto)

    reduzido = dec(custo_conjunto) - dec(receita_liquida_subproduto)
    if memoria is not None:
        memoria.registrar(
            "Custo conjunto liquido de subproduto",
            "custo conjunto - receita liquida do subproduto",
            {
                "custo_conjunto": custo_conjunto,
                "receita_liquida": receita_liquida_subproduto,
            },
            reduzido,
            "BRL",
        )
    return reduzido
