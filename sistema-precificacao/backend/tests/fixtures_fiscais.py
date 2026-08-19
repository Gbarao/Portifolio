"""Regras fiscais minimas para os testes, construidas sem banco.

Usa os proprios modelos ORM desanexados de sessao: sao os mesmos objetos que
o motor recebera em producao, o que evita testar contra um dublê que diverge
do real.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from app.models import FaixaSimplesNacional, RegraTributaria
from app.models.enums import (
    AnexoSimples,
    FormaCalculoBase,
    Recuperabilidade,
    RegimeTributario,
    StatusRegraFiscal,
    TipoOperacaoFiscal,
    TratamentoTributario,
    Tributo,
)

VIGENCIA = date(2026, 1, 1)


def regra(**campos) -> RegraTributaria:
    campos.setdefault("vigencia_inicio", VIGENCIA)
    campos.setdefault("status", StatusRegraFiscal.VALIDADA)
    campos.setdefault("fundamento_legal", "Fundamento de teste")
    campos.setdefault("descricao", campos.get("codigo", "regra"))
    campos.setdefault("versao", 1)
    return RegraTributaria(**campos)


def regras_lucro_real() -> list[RegraTributaria]:
    """PIS/Cofins na venda; IRPJ/CSLL fora de `r` porque incidem sobre lucro."""

    return [
        regra(
            codigo="LR-VENDA-PIS",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.PIS,
            aliquota=D("0.0165"),
            forma_calculo_base=FormaCalculoBase.POR_DENTRO,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
        ),
        regra(
            codigo="LR-VENDA-COFINS",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.COFINS,
            aliquota=D("0.076"),
            forma_calculo_base=FormaCalculoBase.POR_DENTRO,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
        ),
        regra(
            codigo="LR-IRPJ",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.IRPJ,
            aliquota=D("0.15"),
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=False,
            incide_sobre_lucro=True,
        ),
    ]


def regras_lucro_presumido() -> list[RegraTributaria]:
    """PIS/Cofins cumulativos mais a presuncao de IRPJ/CSLL dentro de `r`."""

    return [
        regra(
            codigo="LP-VENDA-PIS",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.PIS,
            aliquota=D("0.0065"),
            forma_calculo_base=FormaCalculoBase.POR_DENTRO,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
        ),
        regra(
            codigo="LP-VENDA-COFINS",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.COFINS,
            aliquota=D("0.03"),
            forma_calculo_base=FormaCalculoBase.POR_DENTRO,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
        ),
        regra(
            codigo="LP-VENDA-IRPJ",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.IRPJ,
            percentual_presuncao_base=D("0.08"),
            aliquota=D("0.15"),
            forma_calculo_base=FormaCalculoBase.BASE_REDUZIDA,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
        ),
        regra(
            codigo="LP-VENDA-CSLL",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.CSLL,
            percentual_presuncao_base=D("0.12"),
            aliquota=D("0.09"),
            forma_calculo_base=FormaCalculoBase.BASE_REDUZIDA,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
        ),
    ]


def regra_credito_condicionado() -> RegraTributaria:
    """Credito da Lei 15.394/2026: so abate com a condicao confirmada."""

    return regra(
        codigo="LR-COMPRA-PIS-CREDITO",
        regime_tributario=RegimeTributario.LUCRO_REAL,
        tipo_operacao=TipoOperacaoFiscal.COMPRA,
        tributo=Tributo.PIS,
        aliquota=D("0.0165"),
        tratamento=TratamentoTributario.CREDITO,
        recuperabilidade=Recuperabilidade.CONDICIONADA,
        percentual_recuperavel=D("1"),
        gera_credito_compra=True,
        requer_confirmacao_condicao=True,
        condicao_descricao="Uso como materia-prima por PJ no lucro real.",
        fundamento_legal="Lei n. 15.394/2026",
    )


def regra_credito_vedado() -> RegraTributaria:
    """Simples Nacional: nenhum credito na aquisicao."""

    return regra(
        codigo="SN-COMPRA-VEDADO",
        regime_tributario=RegimeTributario.SIMPLES_NACIONAL,
        tipo_operacao=TipoOperacaoFiscal.COMPRA,
        tributo=Tributo.ICMS,
        aliquota=D("0.18"),
        tratamento=TratamentoTributario.CREDITO,
        recuperabilidade=Recuperabilidade.VEDADA,
        gera_credito_compra=True,
        compoe_custo_nao_recuperavel=True,
    )


def regra_vencida() -> RegraTributaria:
    """Regra que perdeu vigencia antes da data das operacoes de teste."""

    return regra(
        codigo="LR-VENDA-ICMS-VENCIDA",
        regime_tributario=RegimeTributario.LUCRO_REAL,
        tipo_operacao=TipoOperacaoFiscal.VENDA,
        tributo=Tributo.ICMS,
        aliquota=D("0.18"),
        forma_calculo_base=FormaCalculoBase.POR_DENTRO,
        tratamento=TratamentoTributario.DEBITO,
        compoe_deducao_venda=True,
        vigencia_inicio=date(2025, 1, 1),
        vigencia_fim=date(2025, 12, 31),
        status=StatusRegraFiscal.VALIDADA,
    )


def faixas_anexo_ii() -> list[FaixaSimplesNacional]:
    """Faixas 1 a 4 do Anexo II, suficientes para exercitar a mudanca."""

    linhas = [
        (1, "0", "180000", "0.045", "0", "0.32"),
        (2, "180000.01", "360000", "0.078", "5940", "0.32"),
        (3, "360000.01", "720000", "0.10", "13860", "0.32"),
        (4, "720000.01", "1800000", "0.112", "22500", "0.32"),
    ]
    return [
        FaixaSimplesNacional(
            anexo=AnexoSimples.ANEXO_II,
            ordem_faixa=ordem,
            rbt12_inicio=D(inicio),
            rbt12_fim=D(fim),
            aliquota_nominal=D(nominal),
            parcela_deduzir=D(deduzir),
            percentual_icms=D(icms),
            vigencia_inicio=VIGENCIA,
            status=StatusRegraFiscal.VALIDADA,
        )
        for ordem, inicio, fim, nominal, deduzir, icms in linhas
    ]
