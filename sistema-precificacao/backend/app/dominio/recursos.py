"""Custo de mao de obra, hora-maquina e frota (secoes 6.2 a 6.4).

Nenhum multiplicador universal: o custo do empregado e a soma dos componentes
efetivamente suportados, dividida pelas horas **produtivas praticas** -- nao
pelas horas pagas. Usar horas pagas subestima o custo da hora em cerca de 15%
numa jornada tipica, e esse erro atravessa toda a formacao de preco.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir, percentual_br


# --------------------------------------------------------------------------
# Mao de obra
# --------------------------------------------------------------------------
@dataclass
class FichaEmpregado:
    salario_base: Decimal
    horas_pagas_mes: Decimal
    horas_produtivas_praticas_mes: Decimal
    adicionais: Decimal = ZERO
    horas_extras_media: Decimal = ZERO
    encargos_patronais: Decimal = ZERO
    fgts: Decimal = ZERO
    beneficios: Decimal = ZERO
    provisao_ferias_e_adicional: Decimal = ZERO
    provisao_decimo_terceiro: Decimal = ZERO
    provisao_rescisao: Decimal = ZERO
    epi_uniforme_exames: Decimal = ZERO
    treinamento: Decimal = ZERO
    outros_custos_posto: Decimal = ZERO


@dataclass(frozen=True)
class CustoEmpregado:
    custo_mensal_integral: Decimal
    custo_hora_produtiva: Decimal
    custo_hora_paga: Decimal
    horas_nao_produtivas: Decimal


def calcular_custo_empregado(
    ficha: FichaEmpregado, *, memoria: Memoria | None = None
) -> CustoEmpregado:
    integral = (
        dec(ficha.salario_base)
        + dec(ficha.adicionais)
        + dec(ficha.horas_extras_media)
        + dec(ficha.encargos_patronais)
        + dec(ficha.fgts)
        + dec(ficha.beneficios)
        + dec(ficha.provisao_ferias_e_adicional)
        + dec(ficha.provisao_decimo_terceiro)
        + dec(ficha.provisao_rescisao)
        + dec(ficha.epi_uniforme_exames)
        + dec(ficha.treinamento)
        + dec(ficha.outros_custos_posto)
    )
    por_hora_produtiva = dividir(
        integral, ficha.horas_produtivas_praticas_mes, "custo por hora produtiva"
    )
    por_hora_paga = dividir(integral, ficha.horas_pagas_mes, "custo por hora paga")

    if memoria is not None:
        memoria.registrar(
            "Custo mensal integral do empregado",
            "remuneração + encargos + benefícios + provisões + custos do posto",
            {
                "salario_base": ficha.salario_base,
                "encargos_patronais": ficha.encargos_patronais,
                "beneficios": ficha.beneficios,
                "provisoes": (
                    dec(ficha.provisao_ferias_e_adicional)
                    + dec(ficha.provisao_decimo_terceiro)
                    + dec(ficha.provisao_rescisao)
                ),
            },
            integral,
            "BRL/mes",
        )
        memoria.registrar(
            "Custo por hora produtiva",
            "custo mensal integral / horas produtivas práticas do mês",
            {
                "custo_mensal_integral": integral,
                "horas_produtivas_praticas": ficha.horas_produtivas_praticas_mes,
                "horas_pagas": ficha.horas_pagas_mes,
            },
            por_hora_produtiva,
            "BRL/hora",
        )

    return CustoEmpregado(
        custo_mensal_integral=integral,
        custo_hora_produtiva=por_hora_produtiva,
        custo_hora_paga=por_hora_paga,
        horas_nao_produtivas=dec(ficha.horas_pagas_mes)
        - dec(ficha.horas_produtivas_praticas_mes),
    )


# --------------------------------------------------------------------------
# Maquinas
# --------------------------------------------------------------------------
@dataclass
class FichaMaquina:
    horas_praticas_mes: Decimal
    depreciacao_mensal: Decimal = ZERO
    custo_capital_mensal: Decimal = ZERO
    manutencao_preventiva_mensal: Decimal = ZERO
    seguro_mensal: Decimal = ZERO
    outros_fixos_mensal: Decimal = ZERO
    energia_kwh_por_hora: Decimal = ZERO
    custo_energia_por_kwh: Decimal = ZERO
    agua_m3_por_hora: Decimal = ZERO
    custo_agua_por_m3: Decimal = ZERO
    consumiveis_por_hora: Decimal = ZERO
    manutencao_variavel_por_hora: Decimal = ZERO


@dataclass(frozen=True)
class CustoMaquina:
    custo_fixo_por_hora: Decimal
    custo_variavel_por_hora: Decimal
    custo_total_por_hora: Decimal
    custo_do_uso: Decimal


def calcular_custo_maquina(
    ficha: FichaMaquina,
    horas_efetivas: Decimal,
    *,
    memoria: Memoria | None = None,
) -> CustoMaquina:
    """Custo da hora-maquina sobre a capacidade pratica (secao 6.4)."""

    fixos = (
        dec(ficha.depreciacao_mensal)
        + dec(ficha.custo_capital_mensal)
        + dec(ficha.manutencao_preventiva_mensal)
        + dec(ficha.seguro_mensal)
        + dec(ficha.outros_fixos_mensal)
    )
    fixo_hora = dividir(fixos, ficha.horas_praticas_mes, "custo fixo por hora-maquina")
    variavel_hora = (
        dec(ficha.energia_kwh_por_hora) * dec(ficha.custo_energia_por_kwh)
        + dec(ficha.agua_m3_por_hora) * dec(ficha.custo_agua_por_m3)
        + dec(ficha.consumiveis_por_hora)
        + dec(ficha.manutencao_variavel_por_hora)
    )
    total_hora = fixo_hora + variavel_hora
    custo_uso = total_hora * dec(horas_efetivas)

    if memoria is not None:
        memoria.registrar(
            "Custo fixo por hora-máquina",
            "custos fixos mensais / horas práticas disponíveis",
            {"custos_fixos": fixos, "horas_praticas": ficha.horas_praticas_mes},
            fixo_hora,
            "BRL/hora",
        )
        memoria.registrar(
            "Custo do uso da máquina",
            "horas efetivas × (custo fixo por hora + custo variável por hora)",
            {
                "horas_efetivas": horas_efetivas,
                "custo_fixo_hora": fixo_hora,
                "custo_variavel_hora": variavel_hora,
            },
            custo_uso,
            "BRL",
        )

    return CustoMaquina(
        custo_fixo_por_hora=fixo_hora,
        custo_variavel_por_hora=variavel_hora,
        custo_total_por_hora=total_hora,
        custo_do_uso=custo_uso,
    )


# --------------------------------------------------------------------------
# Frota propria
# --------------------------------------------------------------------------
@dataclass
class FichaVeiculo:
    capacidade_util_kg: Decimal
    km_praticos_mes: Decimal
    horas_praticas_mes: Decimal
    depreciacao_ou_arrendamento_mensal: Decimal = ZERO
    seguro_mensal: Decimal = ZERO
    licenciamento_mensal: Decimal = ZERO
    rastreamento_mensal: Decimal = ZERO
    pessoal_fixo_mensal: Decimal = ZERO
    estrutura_dedicada_mensal: Decimal = ZERO
    custo_capital_mensal: Decimal = ZERO
    combustivel_por_km: Decimal = ZERO
    pneus_por_km: Decimal = ZERO
    manutencao_variavel_por_km: Decimal = ZERO
    lubrificantes_consumiveis_por_km: Decimal = ZERO
    custo_por_hora_operacao: Decimal = ZERO

    @property
    def custo_fixo_mensal(self) -> Decimal:
        return (
            dec(self.depreciacao_ou_arrendamento_mensal)
            + dec(self.seguro_mensal)
            + dec(self.licenciamento_mensal)
            + dec(self.rastreamento_mensal)
            + dec(self.pessoal_fixo_mensal)
            + dec(self.estrutura_dedicada_mensal)
            + dec(self.custo_capital_mensal)
        )

    @property
    def custo_variavel_por_km(self) -> Decimal:
        return (
            dec(self.combustivel_por_km)
            + dec(self.pneus_por_km)
            + dec(self.manutencao_variavel_por_km)
            + dec(self.lubrificantes_consumiveis_por_km)
        )


@dataclass(frozen=True)
class CustoViagem:
    km_totais: Decimal
    custo_variavel: Decimal
    custo_horario: Decimal
    custo_fixo_apropriado: Decimal
    despesas_diretas: Decimal
    custo_total: Decimal
    custo_por_tonelada: Decimal
    ocupacao: Decimal
    custo_km_vazio: Decimal


def calcular_custo_viagem(
    ficha: FichaVeiculo,
    *,
    km_carregado: Decimal,
    km_vazio: Decimal,
    horas_totais: Decimal,
    carga_util_kg: Decimal,
    pedagio: Decimal = ZERO,
    estadia: Decimal = ZERO,
    despesas_especificas: Decimal = ZERO,
    memoria: Memoria | None = None,
) -> CustoViagem:
    """Custo de uma viagem da frota propria.

    O retorno vazio entra no custo por inteiro: sao quilometros rodados,
    combustivel queimado e pneu gasto, mesmo sem carga (caso de teste 6).
    """

    km_totais = dec(km_carregado) + dec(km_vazio)
    variavel = ficha.custo_variavel_por_km * km_totais
    horario = dec(ficha.custo_por_hora_operacao) * dec(horas_totais)

    # Parcela do custo fixo proporcional aos km rodados sobre a capacidade
    # pratica mensal -- o mesmo principio do ABC aplicado a frota.
    fixo_apropriado = (
        dividir(ficha.custo_fixo_mensal, ficha.km_praticos_mes, "custo fixo por km")
        * km_totais
    )
    despesas = dec(pedagio) + dec(estadia) + dec(despesas_especificas)
    total = variavel + horario + fixo_apropriado + despesas

    toneladas = dividir(carga_util_kg, Decimal("1000"), "carga util em toneladas")
    por_tonelada = dividir(total, toneladas, "custo por tonelada entregue")
    ocupacao = dividir(carga_util_kg, ficha.capacidade_util_kg, "ocupacao do veiculo")
    custo_vazio = ficha.custo_variavel_por_km * dec(km_vazio)

    if memoria is not None:
        memoria.registrar(
            "Quilometragem total da viagem",
            "km totais = km carregado + km vazio",
            {"km_carregado": km_carregado, "km_vazio": km_vazio},
            km_totais,
            "km",
            alerta=(
                f"Retorno vazio de {dec(km_vazio)} km representa "
                f"{percentual_br(dividir(km_vazio, km_totais, 'proporção de km vazio'), 1)}"
                f" da viagem."
                if dec(km_vazio) > ZERO
                else None
            ),
        )
        memoria.registrar(
            "Custo da viagem",
            "custo = variável/km × km totais + custo/hora × horas "
            "+ parcela do fixo pela capacidade prática + pedágios e despesas",
            {
                "custo_variavel": variavel,
                "custo_horario": horario,
                "fixo_apropriado": fixo_apropriado,
                "despesas_diretas": despesas,
            },
            total,
            "BRL",
        )
        memoria.registrar(
            "Custo por tonelada entregue",
            "custo da viagem / carga útil efetivamente transportada",
            {"custo_viagem": total, "carga_util_t": toneladas, "ocupacao": ocupacao},
            por_tonelada,
            "BRL/t",
        )

    return CustoViagem(
        km_totais=km_totais,
        custo_variavel=variavel,
        custo_horario=horario,
        custo_fixo_apropriado=fixo_apropriado,
        despesas_diretas=despesas,
        custo_total=total,
        custo_por_tonelada=por_tonelada,
        ocupacao=ocupacao,
        custo_km_vazio=custo_vazio,
    )


@dataclass(frozen=True)
class ComparacaoFrete:
    custo_frota_propria: Decimal
    custo_terceirizado: Decimal
    diferenca: Decimal
    recomendacao: str


def comparar_frete(
    custo_frota_propria: Decimal,
    custo_terceirizado: Decimal,
    *,
    memoria: Memoria | None = None,
) -> ComparacaoFrete:
    """Comparacao exigida pela secao 6.3, sempre sobre o custo cheio da viagem."""

    propria = dec(custo_frota_propria)
    terceiro = dec(custo_terceirizado)
    diferenca = propria - terceiro
    recomendacao = (
        "Frete terceirizado mais barato nesta viagem."
        if diferenca > ZERO
        else "Frota própria mais barata nesta viagem."
    )

    if memoria is not None:
        memoria.registrar(
            "Comparação frota própria × terceiro",
            "diferença = custo da frota própria - custo do terceiro",
            {"frota_propria": propria, "terceirizado": terceiro},
            diferenca,
            "BRL",
            alerta=recomendacao,
        )

    return ComparacaoFrete(
        custo_frota_propria=propria,
        custo_terceirizado=terceiro,
        diferenca=diferenca,
        recomendacao=recomendacao,
    )
