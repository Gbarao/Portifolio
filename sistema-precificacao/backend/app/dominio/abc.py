"""Custeio baseado em atividades (secoes 4.1 e 7.3).

Duas regras estruturais moram aqui:

1. A taxa da atividade divide o pool pela capacidade **pratica**, nunca pela
   utilizacao real. Se o volume cai, a taxa nao sobe: a diferenca vira custo
   de ociosidade do periodo, evidenciado separadamente.
2. Um gasto que ja esta no pool da atividade nao pode ser lancado tambem como
   custo direto do lote. A funcao de transformacao recusa a dupla contagem em
   vez de somar duas vezes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.excecoes import DuplaContagemError
from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir


@dataclass(frozen=True)
class TaxaAtividade:
    """Taxa vigente de uma atividade e sua capacidade pratica."""

    codigo: str
    nome: str
    direcionador: str
    pool_custo: Decimal
    capacidade_pratica: Decimal
    # Parcela fixa do pool: so ela gera ociosidade quando o volume cai.
    # Nulo significa "tratar todo o pool como fixo", a hipotese conservadora.
    percentual_fixo: Decimal | None = None

    @property
    def taxa(self) -> Decimal:
        return dividir(
            self.pool_custo, self.capacidade_pratica, f"taxa da atividade {self.codigo}"
        )


@dataclass(frozen=True)
class ConsumoAtividade:
    """Quantidade de direcionador que o lote consumiu de uma atividade."""

    codigo_atividade: str
    quantidade_direcionador: Decimal


@dataclass
class LancamentoDireto:
    """Custo exclusivo do lote, fora de qualquer pool de atividade.

    ``atividade_de_origem`` deve ficar nulo. Preenche-lo significa que o gasto
    ja esta em um pool -- e nesse caso o lancamento e recusado.
    """

    descricao: str
    valor: Decimal
    atividade_de_origem: str | None = None


@dataclass(frozen=True)
class CustoTransformacao:
    custo_total: Decimal
    custo_por_atividade: dict[str, Decimal]
    custos_diretos: Decimal
    alertas: list[str] = field(default_factory=list)


def calcular_taxa(
    pool_custo: Decimal,
    capacidade_pratica: Decimal,
    *,
    codigo: str = "atividade",
    memoria: Memoria | None = None,
) -> Decimal:
    """Taxa = pool de custos / capacidade pratica do direcionador."""

    taxa = dividir(pool_custo, capacidade_pratica, f"taxa da atividade {codigo}")
    if memoria is not None:
        memoria.registrar(
            f"Taxa da atividade {codigo}",
            "Taxa = pool de custos / capacidade pratica",
            {"pool": pool_custo, "capacidade_pratica": capacidade_pratica},
            taxa,
            "BRL/direcionador",
        )
    return taxa


def calcular_custo_transformacao(
    consumos: list[ConsumoAtividade],
    taxas: dict[str, TaxaAtividade],
    *,
    lancamentos_diretos: list[LancamentoDireto] | None = None,
    memoria: Memoria | None = None,
) -> CustoTransformacao:
    """C_transformacao = Σ (direcionador × taxa) + custos diretos exclusivos."""

    lancamentos_diretos = lancamentos_diretos or []
    atividades_consumidas = {c.codigo_atividade for c in consumos}

    # Guarda contra dupla contagem (regra 12 da secao 11).
    for lancamento in lancamentos_diretos:
        if lancamento.atividade_de_origem in atividades_consumidas:
            raise DuplaContagemError(
                f"O lancamento direto '{lancamento.descricao}' pertence ao pool da "
                f"atividade {lancamento.atividade_de_origem}, ja apropriada por "
                f"direcionador. Remova o lancamento ou retire o gasto do pool."
            )

    custo_por_atividade: dict[str, Decimal] = {}
    total_atividades = ZERO

    for consumo in consumos:
        taxa_atividade = taxas.get(consumo.codigo_atividade)
        if taxa_atividade is None:
            raise KeyError(
                f"Atividade {consumo.codigo_atividade} sem taxa vigente cadastrada."
            )
        taxa = taxa_atividade.taxa
        custo = dec(consumo.quantidade_direcionador) * taxa
        custo_por_atividade[consumo.codigo_atividade] = (
            custo_por_atividade.get(consumo.codigo_atividade, ZERO) + custo
        )
        total_atividades += custo

        if memoria is not None:
            memoria.registrar(
                f"Custo da atividade {taxa_atividade.nome}",
                "custo = quantidade do direcionador × taxa da atividade",
                {
                    "direcionador": taxa_atividade.direcionador,
                    "quantidade": consumo.quantidade_direcionador,
                    "taxa": taxa,
                },
                custo,
                "BRL",
            )

    total_diretos = sum((dec(l.valor) for l in lancamentos_diretos), ZERO)
    if memoria is not None and total_diretos > ZERO:
        memoria.registrar(
            "Custos diretos exclusivos do lote",
            "soma dos lancamentos que nao pertencem a nenhum pool",
            {l.descricao: l.valor for l in lancamentos_diretos},
            total_diretos,
            "BRL",
        )

    total = total_atividades + total_diretos
    if memoria is not None:
        memoria.registrar(
            "Custo de transformacao do lote",
            "C_transformacao = Σ (direcionador × taxa) + custos diretos",
            {"atividades": total_atividades, "diretos": total_diretos},
            total,
            "BRL",
        )

    return CustoTransformacao(
        custo_total=total,
        custo_por_atividade=custo_por_atividade,
        custos_diretos=total_diretos,
    )


@dataclass(frozen=True)
class Ociosidade:
    """Capacidade paga e nao utilizada, por atividade."""

    codigo_atividade: str
    capacidade_pratica: Decimal
    utilizacao_real: Decimal
    capacidade_ociosa: Decimal
    custo_ociosidade: Decimal
    percentual_ocupacao: Decimal


def calcular_ociosidade(
    taxa_atividade: TaxaAtividade,
    utilizacao_real: Decimal,
    *,
    memoria: Memoria | None = None,
) -> Ociosidade:
    """Custo da capacidade nao utilizada no periodo.

    Este valor vai para o resultado do periodo (``fechamento_mensal``), nunca
    para o custo dos produtos: transferi-lo encareceria o produto justamente
    quando o volume caiu, produzindo a espiral de preco que a secao 7.3 proibe.
    """

    capacidade = dec(taxa_atividade.capacidade_pratica)
    utilizada = dec(utilizacao_real)
    ociosa = capacidade - utilizada

    percentual_fixo = (
        dec(taxa_atividade.percentual_fixo)
        if taxa_atividade.percentual_fixo is not None
        else Decimal("1")
    )
    taxa_fixa = taxa_atividade.taxa * percentual_fixo
    custo = ociosa * taxa_fixa if ociosa > ZERO else ZERO
    ocupacao = dividir(utilizada, capacidade, "ocupacao da atividade")

    if memoria is not None:
        memoria.registrar(
            f"Ociosidade da atividade {taxa_atividade.codigo}",
            "custo de ociosidade = (capacidade pratica - utilizacao real) "
            "× taxa fixa da atividade",
            {
                "capacidade_pratica": capacidade,
                "utilizacao_real": utilizada,
                "taxa_fixa": taxa_fixa,
            },
            custo,
            "BRL",
            alerta=(
                f"Ocupacao de {ocupacao:.2%} na atividade {taxa_atividade.codigo}: "
                f"custo de ociosidade lancado ao periodo, nao ao produto."
                if ociosa > ZERO
                else None
            ),
        )

    return Ociosidade(
        codigo_atividade=taxa_atividade.codigo,
        capacidade_pratica=capacidade,
        utilizacao_real=utilizada,
        capacidade_ociosa=ociosa,
        custo_ociosidade=custo,
        percentual_ocupacao=ocupacao,
    )
