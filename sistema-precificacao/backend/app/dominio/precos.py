"""Escada de precos e formacao por margem-alvo (secoes 7.6, 8 e 14).

Formula central, por unidade de venda:

    Receita liquida = P × (1 - r)
    P = C ÷ [(1 - r) × (1 - m)]

onde ``C`` e o custo unitario da camada escolhida, ``r`` a soma das deducoes
proporcionais sobre o preco bruto e ``m`` a margem-alvo medida sobre a receita
liquida. O conteudo de ``r`` e de ``C`` depende do regime tributario e vem do
motor fiscal -- este modulo nao decide aliquota nenhuma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.camadas import (
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
    EstruturaCustos,
)
from app.dominio.excecoes import ParametroInvalidoError
from app.dominio.memoria import Memoria
from app.dominio.unidades import UM, ZERO, dec, dividir, percentual_br

CAMADA_ALVO = "ALVO"
CAMADA_MERCADO = "MERCADO_COMPARAVEL"

# Finalidade de cada degrau, exibida junto ao preco para que nenhum numero
# circule sem rotulo (secao 8).
FINALIDADE_CAMADA = {
    CAMADA_CAIXA: "Decisão excepcional, validade curta e aprovação superior",
    CAMADA_CONTRIBUICAO: "Ocupação de capacidade ociosa no curto prazo",
    CAMADA_OPERACIONAL: "Avaliação da eficiência operacional",
    CAMADA_SUSTENTAVEL: "Piso normal de negociação",
    CAMADA_ALVO: "Proposta comercial padrão",
    CAMADA_MERCADO: "Teste de competitividade; não substitui o custo",
}


@dataclass(frozen=True)
class DegrauPreco:
    camada: str
    custo_unitario: Decimal
    deducoes_r: Decimal
    margem_m: Decimal
    preco_unitario: Decimal
    receita_liquida_unitaria: Decimal
    margem_valor: Decimal
    margem_percentual: Decimal
    finalidade: str
    alerta: str | None = None


@dataclass(frozen=True)
class EscadaPrecos:
    degraus: dict[str, DegrauPreco]
    quantidade: Decimal
    alertas: list[str] = field(default_factory=list)

    def preco(self, camada: str) -> Decimal:
        return self.degraus[camada].preco_unitario

    def avaliar_proposta(self, preco_proposto: Decimal) -> "AvaliacaoProposta":
        return avaliar_proposta(self, preco_proposto)


def _margem_relativa(margem_valor: Decimal, receita_liquida: Decimal) -> Decimal:
    """Margem percentual tolerante a receita liquida nula.

    Uma camada pode legitimamente ter custo zero -- o preco de caixa de um
    lote ja integralmente desembolsado, por exemplo. Nesse caso a margem
    relativa e indefinida, e devolver zero e mais util do que interromper a
    montagem inteira da escada.
    """

    if receita_liquida == ZERO:
        return ZERO
    return dividir(margem_valor, receita_liquida, "margem relativa")


def calcular_preco(
    custo_unitario: Decimal,
    deducoes_r: Decimal,
    margem_m: Decimal,
    *,
    rotulo: str = "preco",
    memoria: Memoria | None = None,
) -> Decimal:
    """P = C ÷ [(1 - r) × (1 - m)].

    ``r`` e ``m`` proximos de 1 explodem o preco -- sinal de premissa errada,
    nao de preco alto. Por isso sao barrados antes da divisao.
    """

    r = dec(deducoes_r)
    m = dec(margem_m)

    if r >= UM:
        raise ParametroInvalidoError(
            f"Deduções de {percentual_br(r)} sobre o preço bruto tornam a receita "
            f"líquida nula ou negativa. Revise a matriz tributária antes de "
            f"precificar."
        )
    if m >= UM:
        raise ParametroInvalidoError(
            f"Margem-alvo de {percentual_br(m)} da receita líquida é inatingível "
            f"por construção."
        )

    denominador = (UM - r) * (UM - m)
    preco = dividir(custo_unitario, denominador, f"formacao de {rotulo}")

    if memoria is not None:
        memoria.registrar(
            f"Formação do {rotulo}",
            "P = C / [(1 - r) × (1 - m)]",
            {"C": custo_unitario, "r": r, "m": m},
            preco,
            "BRL/kg",
        )

    return preco


def montar_escada(
    estrutura: EstruturaCustos,
    *,
    deducoes_r: Decimal,
    margem_contribuicao_minima: Decimal,
    margem_alvo: Decimal,
    preco_mercado: Decimal | None = None,
    quantidade: Decimal | None = None,
    memoria: Memoria | None = None,
) -> EscadaPrecos:
    """Monta os cinco degraus obrigatorios mais o preco de mercado comparavel.

    O preco de caixa nao carrega margem: por definicao cobre apenas o
    desembolso incremental e as deducoes da venda. Ele existe para decisao
    excepcional, e a escada deixa isso explicito na finalidade de cada degrau.
    """

    quantidade = dec(quantidade if quantidade is not None else estrutura.quantidade_vendavel)
    r = dec(deducoes_r)

    configuracao = [
        (CAMADA_CAIXA, estrutura.unitario(CAMADA_CAIXA), ZERO),
        (
            CAMADA_CONTRIBUICAO,
            estrutura.unitario(CAMADA_CONTRIBUICAO),
            dec(margem_contribuicao_minima),
        ),
        (CAMADA_OPERACIONAL, estrutura.unitario(CAMADA_OPERACIONAL), ZERO),
        (CAMADA_SUSTENTAVEL, estrutura.unitario(CAMADA_SUSTENTAVEL), ZERO),
        (CAMADA_ALVO, estrutura.unitario(CAMADA_SUSTENTAVEL), dec(margem_alvo)),
    ]

    degraus: dict[str, DegrauPreco] = {}
    for camada, custo, margem in configuracao:
        preco = calcular_preco(
            custo, r, margem, rotulo=f"preço {camada.lower()}", memoria=memoria
        )
        receita_liquida = preco * (UM - r)
        degraus[camada] = DegrauPreco(
            camada=camada,
            custo_unitario=custo,
            deducoes_r=r,
            margem_m=margem,
            preco_unitario=preco,
            receita_liquida_unitaria=receita_liquida,
            margem_valor=receita_liquida - custo,
            margem_percentual=_margem_relativa(receita_liquida - custo, receita_liquida),
            finalidade=FINALIDADE_CAMADA[camada],
        )

    if preco_mercado is not None:
        preco_mercado = dec(preco_mercado)
        receita_liquida = preco_mercado * (UM - r)
        custo_sustentavel = estrutura.unitario(CAMADA_SUSTENTAVEL)
        degraus[CAMADA_MERCADO] = DegrauPreco(
            camada=CAMADA_MERCADO,
            custo_unitario=custo_sustentavel,
            deducoes_r=r,
            margem_m=ZERO,
            preco_unitario=preco_mercado,
            receita_liquida_unitaria=receita_liquida,
            margem_valor=receita_liquida - custo_sustentavel,
            margem_percentual=_margem_relativa(
                receita_liquida - custo_sustentavel, receita_liquida
            ),
            finalidade=FINALIDADE_CAMADA[CAMADA_MERCADO],
        )

    alertas: list[str] = []
    if preco_mercado is not None and preco_mercado < degraus[CAMADA_SUSTENTAVEL].preco_unitario:
        alertas.append(
            "Preço de mercado abaixo do preço sustentável: operar neste nível "
            "não cobre a estrutura no longo prazo."
        )

    return EscadaPrecos(degraus=degraus, quantidade=quantidade, alertas=alertas)


@dataclass(frozen=True)
class AvaliacaoProposta:
    """Classificacao de um preco proposto contra a escada (secao 13.2)."""

    preco_proposto: Decimal
    faixa: str
    alcada_necessaria: str
    valor_concessao: Decimal
    bloqueado: bool
    mensagem: str


def avaliar_proposta(escada: EscadaPrecos, preco_proposto: Decimal) -> AvaliacaoProposta:
    """Enquadra a proposta na politica de alcadas.

    Nenhum preco abaixo do sustentavel e apresentado como rentavel: a avaliacao
    devolve o valor da concessao e a alcada necessaria para aprova-la.
    """

    preco = dec(preco_proposto)
    alvo = escada.degraus[CAMADA_ALVO].preco_unitario
    sustentavel = escada.degraus[CAMADA_SUSTENTAVEL].preco_unitario
    contribuicao = escada.degraus[CAMADA_CONTRIBUICAO].preco_unitario
    caixa = escada.degraus[CAMADA_CAIXA].preco_unitario

    if preco >= alvo:
        return AvaliacaoProposta(
            preco_proposto=preco,
            faixa="IGUAL_OU_ACIMA_DO_ALVO",
            alcada_necessaria="Fluxo comercial normal",
            valor_concessao=ZERO,
            bloqueado=False,
            mensagem="Preço igual ou superior ao alvo.",
        )

    concessao = (alvo - preco) * escada.quantidade

    if preco >= sustentavel:
        return AvaliacaoProposta(
            preco_proposto=preco,
            faixa="ENTRE_ALVO_E_SUSTENTAVEL",
            alcada_necessaria="Gestor comercial",
            valor_concessao=concessao,
            bloqueado=False,
            mensagem="Abaixo do alvo, mas acima do piso sustentável.",
        )

    if preco >= contribuicao:
        return AvaliacaoProposta(
            preco_proposto=preco,
            faixa="ENTRE_SUSTENTAVEL_E_CONTRIBUICAO",
            alcada_necessaria="Controladoria e diretoria, com prazo definido",
            valor_concessao=concessao,
            bloqueado=False,
            mensagem=(
                "Abaixo do preço sustentável: contribui no curto prazo, mas não "
                "sustenta a estrutura. Exige motivo, prazo e responsável."
            ),
        )

    if preco >= caixa:
        return AvaliacaoProposta(
            preco_proposto=preco,
            faixa="ABAIXO_DA_CONTRIBUICAO",
            alcada_necessaria="Decisão estratégica formal da diretoria",
            valor_concessao=concessao,
            bloqueado=True,
            mensagem=(
                "Abaixo da margem de contribuição mínima: bloqueado salvo decisão "
                "estratégica com valor máximo de perda definido."
            ),
        )

    return AvaliacaoProposta(
        preco_proposto=preco,
        faixa="CAIXA_INCREMENTAL_NEGATIVO",
        alcada_necessaria="Bloqueado",
        valor_concessao=concessao,
        bloqueado=True,
        mensagem=(
            "O preço não cobre nem o desembolso incremental da operação: cada "
            "tonelada vendida consome caixa."
        ),
    )


# --------------------------------------------------------------------------
# Simulacoes obrigatorias (secao 14)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PrecoMaximoCompra:
    receita_liquida_total: Decimal
    demais_custos: Decimal
    lucro_alvo: Decimal
    preco_maximo_total: Decimal
    preco_maximo_unitario: Decimal


def calcular_preco_maximo_compra(
    *,
    preco_venda_unitario: Decimal,
    quantidade_vendavel: Decimal,
    deducoes_r: Decimal,
    demais_custos: Decimal,
    margem_alvo: Decimal,
    quantidade_aceita_esperada: Decimal,
    memoria: Memoria | None = None,
) -> PrecoMaximoCompra:
    """Quanto se pode pagar pelo material dado um preco de venda conhecido.

    E o calculo mais util do modelo quando o preco de venda e ditado pelo
    mercado e a decisao real esta na compra. O divisor e a quantidade
    **aceita**, nao a vendavel: paga-se pelo que entra, vende-se o que sobra.
    """

    receita_liquida = (
        dec(preco_venda_unitario) * dec(quantidade_vendavel) * (UM - dec(deducoes_r))
    )
    lucro = receita_liquida * dec(margem_alvo)
    maximo_total = receita_liquida - dec(demais_custos) - lucro
    maximo_unitario = dividir(
        maximo_total, quantidade_aceita_esperada, "preco maximo unitario de compra"
    )

    if memoria is not None:
        memoria.registrar(
            "Receita líquida esperada",
            "receita líquida = preço de venda × quantidade vendável × (1 - r)",
            {
                "preco_venda": preco_venda_unitario,
                "Q_vendavel": quantidade_vendavel,
                "r": deducoes_r,
            },
            receita_liquida,
            "BRL",
        )
        memoria.registrar(
            "Preço máximo total de compra",
            "receita líquida - demais custos e despesas - lucro-alvo",
            {
                "receita_liquida": receita_liquida,
                "demais_custos": demais_custos,
                "lucro_alvo": lucro,
            },
            maximo_total,
            "BRL",
        )
        memoria.registrar(
            "Preço máximo unitário de compra",
            "preço máximo total / quantidade aceita esperada",
            {
                "preco_maximo_total": maximo_total,
                "Q_aceita_esperada": quantidade_aceita_esperada,
            },
            maximo_unitario,
            "BRL/kg",
        )

    return PrecoMaximoCompra(
        receita_liquida_total=receita_liquida,
        demais_custos=dec(demais_custos),
        lucro_alvo=lucro,
        preco_maximo_total=maximo_total,
        preco_maximo_unitario=maximo_unitario,
    )


def calcular_preco_minimo_venda(
    *,
    custo_unitario: Decimal,
    deducoes_r: Decimal,
    margem_minima: Decimal = ZERO,
    memoria: Memoria | None = None,
) -> Decimal:
    """Menor preco que cobre o custo informado e a margem minima exigida."""

    return calcular_preco(
        custo_unitario,
        deducoes_r,
        margem_minima,
        rotulo="preço mínimo de venda",
        memoria=memoria,
    )
