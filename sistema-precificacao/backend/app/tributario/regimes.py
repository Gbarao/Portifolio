"""Composicao de `r` e de `C` por regime tributario (secoes 7.7 e 9.4).

O sistema nunca soma IRPJ e CSLL aos tributos sobre a venda sem regra
validada. Quem decide se um tributo entra em `r` e a propria regra
(``compoe_deducao_venda``), e as seeds ja tratam a diferenca entre regimes:

* **Lucro Real** -- IRPJ/CSLL marcados ``incide_sobre_lucro`` ficam fora de
  `r`; a margem-alvo e, portanto, margem antes desses tributos.
* **Lucro Presumido** -- a presuncao torna IRPJ/CSLL percentuais lineares
  sobre a receita bruta, e eles entram em `r`.
* **Simples Nacional** -- `r` e a aliquota efetiva do DAS, calculada a partir
  da RBT12, com possibilidade de segregar o ICMS diferido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from app.dominio.excecoes import ParametroInvalidoError
from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir, percentual_br
from app.tributario.calculo import aplicar_regra
from app.tributario.resolucao import ContextoFiscal, resolver
from app.tributario.resultado import ApuracaoOperacao, ResultadoTributo

REGIME_LUCRO_REAL = "LUCRO_REAL"
REGIME_LUCRO_PRESUMIDO = "LUCRO_PRESUMIDO"
REGIME_SIMPLES = "SIMPLES_NACIONAL"


@dataclass
class DeducoesVenda:
    """Variavel `r` decomposta, para que o usuario veja de onde ela veio."""

    r_total: Decimal
    detalhamento: dict[str, Decimal] = field(default_factory=dict)
    apuracao: ApuracaoOperacao = field(default_factory=ApuracaoOperacao)
    alertas: list[str] = field(default_factory=list)

    @property
    def permite_cotacao_definitiva(self) -> bool:
        return self.apuracao.permite_cotacao_definitiva


def calcular_deducoes_venda(
    regras: Iterable[Any],
    contexto: ContextoFiscal,
    *,
    preco_bruto_referencia: Decimal = Decimal("1"),
    comissao_percentual: Decimal = ZERO,
    desconto_contratual_percentual: Decimal = ZERO,
    memoria: Memoria | None = None,
) -> DeducoesVenda:
    """Soma as deducoes proporcionais sobre o preco bruto.

    Alem dos tributos, `r` inclui comissao percentual e desconto contratual
    esperado -- a secao 7.6 e explicita quanto a isso.
    """

    resolucao = resolver(regras, contexto)
    apuracao = ApuracaoOperacao(alertas=list(resolucao.alertas))

    detalhamento: dict[str, Decimal] = {}
    total = ZERO

    for regra in resolucao.aplicaveis:
        resultado = aplicar_regra(
            regra,
            base_bruta=dec(preco_bruto_referencia),
            data_operacao=contexto.data_operacao,
            memoria=memoria,
        )
        apuracao.resultados.append(resultado)
        if resultado.efeito_percentual_sobre_preco > ZERO:
            detalhamento[resultado.tributo] = resultado.efeito_percentual_sobre_preco
            total += resultado.efeito_percentual_sobre_preco

    # Regras vencidas nao entram no calculo, mas contaminam o status.
    for regra in resolucao.vencidas:
        apuracao.resultados.append(
            ResultadoTributo(
                tributo=str(getattr(getattr(regra, "tributo", ""), "value", regra.tributo)),
                tipo_operacao=contexto.tipo_operacao,
                base_calculo=ZERO,
                aliquota_nominal=ZERO,
                aliquota_efetiva=ZERO,
                valor_destacado=ZERO,
                valor_devido=ZERO,
                codigo_regra=getattr(regra, "codigo", None),
                status="VENCIDA",
                alerta="Regra fora de vigencia na data da operacao.",
            )
        )

    if dec(comissao_percentual) > ZERO:
        detalhamento["COMISSAO"] = dec(comissao_percentual)
        total += dec(comissao_percentual)
    if dec(desconto_contratual_percentual) > ZERO:
        detalhamento["DESCONTO_CONTRATUAL"] = dec(desconto_contratual_percentual)
        total += dec(desconto_contratual_percentual)

    if memoria is not None:
        memoria.registrar(
            "Deduções proporcionais sobre o preço (r)",
            "r = Σ efeitos percentuais das regras que compõem dedução de venda "
            "+ comissão + desconto contratual",
            {k: v for k, v in detalhamento.items()},
            total,
            "fracao",
            status_dado=apuracao.status_consolidado,
            alerta=(
                None
                if apuracao.permite_cotacao_definitiva
                else (
                    f"Status fiscal {apuracao.status_consolidado}: a cotação não "
                    f"pode ser classificada como definitiva."
                )
            ),
        )

    return DeducoesVenda(
        r_total=total,
        detalhamento=detalhamento,
        apuracao=apuracao,
        alertas=list(apuracao.alertas),
    )


@dataclass
class CreditosCompra:
    """Creditos apurados na aquisicao, separados por aproveitamento."""

    creditos_confirmados: Decimal
    creditos_condicionados: Decimal
    creditos_vedados: Decimal
    apuracao: ApuracaoOperacao = field(default_factory=ApuracaoOperacao)


def calcular_creditos_compra(
    regras: Iterable[Any],
    contexto: ContextoFiscal,
    *,
    valor_compra: Decimal,
    condicoes_confirmadas: dict[str, bool] | None = None,
    memoria: Memoria | None = None,
) -> CreditosCompra:
    """Apura os creditos da aquisicao e separa o que pode abater o custo.

    ``condicoes_confirmadas`` mapeia o codigo da regra para a confirmacao
    documental. Nao informar equivale a nao confirmar -- a hipotese
    conservadora exigida pela secao 6.1.
    """

    condicoes_confirmadas = condicoes_confirmadas or {}
    resolucao = resolver(regras, contexto)
    apuracao = ApuracaoOperacao(alertas=list(resolucao.alertas))

    confirmados = ZERO
    condicionados = ZERO
    vedados = ZERO

    for regra in resolucao.aplicaveis:
        codigo = getattr(regra, "codigo", None)
        resultado = aplicar_regra(
            regra,
            base_bruta=dec(valor_compra),
            data_operacao=contexto.data_operacao,
            condicao_confirmada=condicoes_confirmadas.get(codigo, False),
            memoria=memoria,
        )
        apuracao.resultados.append(resultado)

        if resultado.recuperabilidade == "VEDADA":
            vedados += resultado.credito_entrada_relacionado
        elif resultado.valor_recuperavel > ZERO:
            confirmados += resultado.valor_recuperavel
        elif resultado.credito_entrada_relacionado > ZERO:
            condicionados += resultado.credito_entrada_relacionado

    if memoria is not None:
        memoria.registrar(
            "Créditos fiscais da aquisição",
            "somente créditos elegíveis e confirmados reduzem o custo",
            {
                "confirmados": confirmados,
                "condicionados": condicionados,
                "vedados": vedados,
            },
            confirmados,
            "BRL",
            alerta=(
                f"Créditos condicionados de {condicionados} aguardam confirmação "
                f"e não reduziram o custo."
                if condicionados > ZERO
                else None
            ),
        )

    return CreditosCompra(
        creditos_confirmados=confirmados,
        creditos_condicionados=condicionados,
        creditos_vedados=vedados,
        apuracao=apuracao,
    )


# --------------------------------------------------------------------------
# Simples Nacional: aliquota efetiva, segregacao de ICMS e mudanca de faixa
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AliquotaSimples:
    rbt12: Decimal
    ordem_faixa: int
    aliquota_nominal: Decimal
    parcela_deduzir: Decimal
    aliquota_efetiva: Decimal
    aliquota_efetiva_sem_icms: Decimal
    percentual_icms: Decimal


def localizar_faixa(faixas: Iterable[Any], rbt12: Decimal, anexo: str) -> Any:
    """Encontra a faixa do anexo que contem a RBT12 informada."""

    valor = dec(rbt12)
    for faixa in faixas:
        if str(getattr(getattr(faixa, "anexo", ""), "value", faixa.anexo)) != anexo:
            continue
        if dec(faixa.rbt12_inicio) <= valor <= dec(faixa.rbt12_fim):
            return faixa
    raise ParametroInvalidoError(
        f"RBT12 de {valor} não se enquadra em nenhuma faixa cadastrada do {anexo}. "
        f"Acima do limite do Simples ou tabela incompleta."
    )


def calcular_aliquota_efetiva_simples(
    faixas: Iterable[Any],
    *,
    rbt12: Decimal,
    anexo: str,
    icms_segregado: bool = False,
    memoria: Memoria | None = None,
) -> AliquotaSimples:
    """Aliquota efetiva do DAS: (RBT12 × nominal - parcela a deduzir) / RBT12.

    Quando a operacao com sucata goza de isencao ou diferimento estadual, a
    parcela de ICMS e segregada do DAS -- caso contrario a empresa recolheria
    dentro do unificado um tributo que a legislacao estadual ja afastou
    (secao 9.4-3).
    """

    faixas = list(faixas)
    rbt = dec(rbt12)
    if rbt <= ZERO:
        raise ParametroInvalidoError(
            "RBT12 igual a zero: empresa em início de atividade exige regra de "
            "proporcionalização específica, ainda não parametrizada."
        )

    faixa = localizar_faixa(faixas, rbt, anexo)
    nominal = dec(faixa.aliquota_nominal)
    deduzir = dec(faixa.parcela_deduzir)
    efetiva = dividir(rbt * nominal - deduzir, rbt, "aliquota efetiva do Simples")
    percentual_icms = dec(getattr(faixa, "percentual_icms", ZERO))
    efetiva_sem_icms = efetiva * (Decimal("1") - percentual_icms)

    if memoria is not None:
        memoria.registrar(
            "Alíquota efetiva do Simples Nacional",
            "efetiva = (RBT12 × alíquota nominal - parcela a deduzir) / RBT12",
            {
                "RBT12": rbt,
                "anexo": anexo,
                "faixa": faixa.ordem_faixa,
                "aliquota_nominal": nominal,
                "parcela_deduzir": deduzir,
            },
            efetiva,
            "fracao",
            fonte=getattr(faixa, "fundamento_legal", None),
        )
        if icms_segregado:
            memoria.registrar(
                "Alíquota efetiva sem a parcela de ICMS",
                "efetiva × (1 - percentual de ICMS da faixa)",
                {"efetiva": efetiva, "percentual_icms": percentual_icms},
                efetiva_sem_icms,
                "fracao",
                alerta=(
                    "ICMS segregado do DAS por isenção ou diferimento estadual: "
                    "confirmar enquadramento com o responsável fiscal."
                ),
            )

    return AliquotaSimples(
        rbt12=rbt,
        ordem_faixa=int(faixa.ordem_faixa),
        aliquota_nominal=nominal,
        parcela_deduzir=deduzir,
        aliquota_efetiva=efetiva,
        aliquota_efetiva_sem_icms=efetiva_sem_icms,
        percentual_icms=percentual_icms,
    )


@dataclass(frozen=True)
class ImpactoMudancaFaixa:
    """O alerta critico da secao 7.7-C.

    Se a venda empurra a RBT12 para a faixa seguinte, a aliquota nao sobe so
    para ela: sobe para todo o faturamento do mes. O custo tributario marginal
    dessa venda e, portanto, muito maior que o aparente.
    """

    rbt12_antes: Decimal
    rbt12_depois: Decimal
    faixa_antes: int
    faixa_depois: int
    aliquota_antes: Decimal
    aliquota_depois: Decimal
    das_sem_a_venda: Decimal
    das_com_a_venda: Decimal
    das_adicional: Decimal
    das_adicional_atribuivel_a_venda: Decimal
    aliquota_marginal_da_venda: Decimal
    mudou_de_faixa: bool
    alerta: str | None


def simular_mudanca_faixa(
    faixas: Iterable[Any],
    *,
    rbt12_atual: Decimal,
    receita_mes_sem_a_venda: Decimal,
    receita_da_venda: Decimal,
    anexo: str,
    memoria: Memoria | None = None,
) -> ImpactoMudancaFaixa:
    """Compara o DAS do mes com e sem a venda analisada."""

    faixas = list(faixas)
    rbt_antes = dec(rbt12_atual)
    rbt_depois = rbt_antes + dec(receita_da_venda)

    antes = calcular_aliquota_efetiva_simples(faixas, rbt12=rbt_antes, anexo=anexo)
    depois = calcular_aliquota_efetiva_simples(faixas, rbt12=rbt_depois, anexo=anexo)

    receita_sem = dec(receita_mes_sem_a_venda)
    receita_com = receita_sem + dec(receita_da_venda)

    # Sem a venda, o mes inteiro e tributado pela aliquota antiga.
    das_sem = receita_sem * antes.aliquota_efetiva
    # Com a venda, a aliquota nova alcanca todo o faturamento do mes.
    das_com = receita_com * depois.aliquota_efetiva
    adicional = das_com - das_sem

    # Parcela do adicional que excede o DAS "justo" da propria venda: e o
    # custo escondido que a mudanca de faixa joga sobre o faturamento antigo.
    das_justo_da_venda = dec(receita_da_venda) * antes.aliquota_efetiva
    adicional_atribuivel = adicional - das_justo_da_venda

    marginal = dividir(
        adicional, dec(receita_da_venda), "aliquota marginal da venda"
    ) if dec(receita_da_venda) > ZERO else ZERO

    mudou = depois.ordem_faixa != antes.ordem_faixa
    alerta = None
    if mudou:
        alerta = (
            f"Esta venda muda a faixa do Simples da {antes.ordem_faixa} para a "
            f"{depois.ordem_faixa}: a alíquota efetiva sobe de "
            f"{percentual_br(antes.aliquota_efetiva, 4)} para "
            f"{percentual_br(depois.aliquota_efetiva, 4)} e passa a incidir sobre "
            f"todo o faturamento do mês. O custo tributário marginal desta venda é "
            f"de {percentual_br(marginal, 4)}, e não "
            f"{percentual_br(antes.aliquota_efetiva, 4)}."
        )

    if memoria is not None:
        memoria.registrar(
            "Impacto da venda na faixa do Simples",
            "DAS adicional = receita do mês com a venda × alíquota nova "
            "- receita do mês sem a venda × alíquota anterior",
            {
                "RBT12_antes": rbt_antes,
                "RBT12_depois": rbt_depois,
                "aliquota_antes": antes.aliquota_efetiva,
                "aliquota_depois": depois.aliquota_efetiva,
                "receita_mes_sem_venda": receita_sem,
                "receita_da_venda": receita_da_venda,
            },
            adicional,
            "BRL",
            alerta=alerta,
        )

    return ImpactoMudancaFaixa(
        rbt12_antes=rbt_antes,
        rbt12_depois=rbt_depois,
        faixa_antes=antes.ordem_faixa,
        faixa_depois=depois.ordem_faixa,
        aliquota_antes=antes.aliquota_efetiva,
        aliquota_depois=depois.aliquota_efetiva,
        das_sem_a_venda=das_sem,
        das_com_a_venda=das_com,
        das_adicional=adicional,
        das_adicional_atribuivel_a_venda=adicional_atribuivel,
        aliquota_marginal_da_venda=marginal,
        mudou_de_faixa=mudou,
        alerta=alerta,
    )
