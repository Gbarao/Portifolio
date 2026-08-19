"""Custo liquido de aquisicao do lote (secoes 6.1 e 7.2).

Regra inegociavel: credito fiscal so reduz o custo quando confirmado,
documentado, apropriavel e com expectativa razoavel de realizacao. Credito
condicionado entra em campo proprio, gera alerta e **nao** abate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir


@dataclass
class EntradasAquisicao:
    """Componentes do custo de aquisicao, na ordem da secao 7.2."""

    preco_bruto: Decimal
    descontos: Decimal = ZERO
    bonificacoes: Decimal = ZERO
    tributos_nao_recuperaveis: Decimal = ZERO
    frete_entrada: Decimal = ZERO
    seguro_entrada: Decimal = ZERO
    pedagio: Decimal = ZERO
    coleta_carga_descarga: Decimal = ZERO
    pesagem_inspecao: Decimal = ZERO
    embalagem_nao_retornavel: Decimal = ZERO
    comissao_compra: Decimal = ZERO
    destinacao_rejeito: Decimal = ZERO
    outros_custos: Decimal = ZERO
    creditos_confirmados: Decimal = ZERO
    # Creditos que dependem de condicao ainda nao confirmada (ex.: Lei
    # 15.394/2026 sem comprovacao do uso como materia-prima). Informativos.
    creditos_condicionados: Decimal = ZERO


@dataclass(frozen=True)
class CustoAquisicao:
    custo_total: Decimal
    custo_por_kg_aceito: Decimal
    custo_por_kg_vendavel: Decimal
    creditos_abatidos: Decimal
    creditos_pendentes: Decimal
    alertas: list[str] = field(default_factory=list)


def calcular_custo_aquisicao(
    entradas: EntradasAquisicao,
    *,
    quantidade_aceita: Decimal,
    quantidade_vendavel: Decimal,
    memoria: Memoria | None = None,
) -> CustoAquisicao:
    """Calcula o custo de aquisicao e o distribui pela quantidade correta.

    O custo por quilograma vendavel e maior que o custo por quilograma aceito
    sempre que houver perda ou rejeito -- e esse o mecanismo que transfere o
    custo da perda para a quantidade que sera efetivamente vendida.
    """

    alertas: list[str] = []

    gastos_adicionais = (
        dec(entradas.tributos_nao_recuperaveis)
        + dec(entradas.frete_entrada)
        + dec(entradas.seguro_entrada)
        + dec(entradas.pedagio)
        + dec(entradas.coleta_carga_descarga)
        + dec(entradas.pesagem_inspecao)
        + dec(entradas.embalagem_nao_retornavel)
        + dec(entradas.comissao_compra)
        + dec(entradas.destinacao_rejeito)
        + dec(entradas.outros_custos)
    )

    creditos_abatidos = dec(entradas.creditos_confirmados)
    creditos_pendentes = dec(entradas.creditos_condicionados)

    if creditos_pendentes > ZERO:
        alertas.append(
            f"Crédito condicionado de {creditos_pendentes} não reduziu o custo: "
            f"depende de confirmação documental antes de ser apropriado."
        )

    custo_total = (
        dec(entradas.preco_bruto)
        - dec(entradas.descontos)
        - dec(entradas.bonificacoes)
        + gastos_adicionais
        - creditos_abatidos
    )

    por_aceito = dividir(custo_total, quantidade_aceita, "custo por kg aceito")
    por_vendavel = dividir(custo_total, quantidade_vendavel, "custo por kg vendavel")

    if memoria is not None:
        memoria.registrar(
            "Custo líquido de aquisição",
            "C_aquisicao = preço bruto - descontos - bonificações "
            "+ tributos não recuperáveis + frete e demais custos atribuíveis "
            "- créditos fiscais confirmados",
            {
                "preco_bruto": entradas.preco_bruto,
                "descontos": entradas.descontos,
                "bonificacoes": entradas.bonificacoes,
                "gastos_adicionais": gastos_adicionais,
                "creditos_confirmados": creditos_abatidos,
            },
            custo_total,
            "BRL",
            alerta=alertas[0] if alertas else None,
        )
        memoria.registrar(
            "Custo por kg aceito",
            "C_aquisicao / Q_aceita",
            {"C_aquisicao": custo_total, "Q_aceita": quantidade_aceita},
            por_aceito,
            "BRL/kg",
        )
        memoria.registrar(
            "Custo por kg vendável",
            "C_aquisicao / Q_vendavel",
            {"C_aquisicao": custo_total, "Q_vendavel": quantidade_vendavel},
            por_vendavel,
            "BRL/kg",
        )
        if creditos_pendentes > ZERO:
            memoria.registrar(
                "Crédito condicionado (informativo)",
                "valor mantido fora do custo até confirmação",
                {"credito_condicionado": creditos_pendentes},
                creditos_pendentes,
                "BRL",
                status_dado="PROVISORIO",
                alerta=alertas[0],
            )

    return CustoAquisicao(
        custo_total=custo_total,
        custo_por_kg_aceito=por_aceito,
        custo_por_kg_vendavel=por_vendavel,
        creditos_abatidos=creditos_abatidos,
        creditos_pendentes=creditos_pendentes,
        alertas=alertas,
    )
