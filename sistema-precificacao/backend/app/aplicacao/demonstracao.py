"""Demonstracao executavel: um lote real percorrendo o motor inteiro.

Roda com ``python -m app.aplicacao.demonstracao``. Nao depende de banco --
usa as regras de exemplo para mostrar, lado a lado, como o mesmo lote produz
precos diferentes em cada regime tributario.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from app.dominio.abc import ConsumoAtividade, TaxaAtividade, calcular_custo_transformacao
from app.dominio.aquisicao import EntradasAquisicao, calcular_custo_aquisicao
from app.dominio.camadas import (
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
    ComponenteCusto,
    VISAO_GERENCIAL,
    montar_estrutura,
)
from app.dominio.capital import CicloFinanceiro, calcular_custo_capital
from app.dominio.massa import calcular_balanco
from app.dominio.memoria import Memoria
from app.dominio.precos import CAMADA_ALVO, montar_escada
from app.dominio.unidades import arredondar
from app.tributario.regimes import calcular_deducoes_venda, simular_mudanca_faixa
from app.seeds.demo import construir_faixas_simples, construir_regras_tributarias
from app.tributario.resolucao import ContextoFiscal

DATA = date(2026, 3, 10)


def _regras_por_regime(regime: str):
    """Regras de demonstracao, as mesmas das seeds.

    Elas nascem com status PROVISORIA de proposito: e assim que o sistema se
    comporta antes de o responsavel fiscal validar a matriz.
    """

    return [
        regra
        for regra in construir_regras_tributarias()
        if getattr(regra.regime_tributario, "value", regra.regime_tributario) == regime
    ]


def calcular_lote(memoria: Memoria):
    """Lote LC-2026-000001: 12.000 kg de papelao misto."""

    balanco = calcular_balanco(
        peso_bruto=D("15500"),
        tara=D("3500"),
        quantidade_recusada=D("400"),
        quantidade_vendavel=D("10440"),
        quantidade_rejeito=D("800"),
        perda_normal=D("360"),
        tolerancia=D("0.02"),
        memoria=memoria,
    )

    aquisicao = calcular_custo_aquisicao(
        EntradasAquisicao(
            preco_bruto=D("0.42") * D("12000"),
            descontos=D("168"),
            frete_entrada=D("380"),
            pedagio=D("42"),
            coleta_carga_descarga=D("120"),
            pesagem_inspecao=D("35"),
            destinacao_rejeito=D("96"),
        ),
        quantidade_aceita=balanco.quantidade_aceita,
        quantidade_vendavel=balanco.quantidade_vendavel,
        memoria=memoria,
    )

    taxas = {
        "ATV-REC": TaxaAtividade("ATV-REC", "Recebimento", "NUMERO_RECEBIMENTOS", D("4800"), D("120")),
        "ATV-TRI": TaxaAtividade("ATV-TRI", "Triagem", "HORA_MAO_DE_OBRA", D("27600"), D("1200")),
        "ATV-PRE": TaxaAtividade("ATV-PRE", "Prensagem", "HORA_MAQUINA", D("6300"), D("280")),
        "ATV-ARM": TaxaAtividade("ATV-ARM", "Armazenagem", "TONELADA_DIA", D("12400"), D("9000")),
    }
    transformacao = calcular_custo_transformacao(
        [
            ConsumoAtividade("ATV-REC", D("1")),
            ConsumoAtividade("ATV-TRI", D("6")),
            ConsumoAtividade("ATV-PRE", D("2.5")),
            ConsumoAtividade("ATV-ARM", D("52.2")),
        ],
        taxas,
        memoria=memoria,
    )

    capital = calcular_custo_capital(
        capital_comprometido=aquisicao.custo_total,
        ciclo=CicloFinanceiro(dias_estoque=12, dias_recebimento=30, dias_pagamento=7),
        taxa_anual=D("0.18"),
        memoria=memoria,
    )

    return balanco, aquisicao, transformacao, capital


def montar_componentes(aquisicao, transformacao, capital) -> list[ComponenteCusto]:
    return [
        ComponenteCusto("Aquisicao do lote", aquisicao.custo_total, CAMADA_CAIXA),
        ComponenteCusto(
            "Transformacao (ABC)", transformacao.custo_total, CAMADA_CONTRIBUICAO
        ),
        ComponenteCusto(
            "Estrutura produtiva alocada", D("640"), CAMADA_OPERACIONAL, e_desembolso=False
        ),
        ComponenteCusto(
            "Despesas administrativas e comerciais",
            D("780"),
            CAMADA_SUSTENTAVEL,
            visoes=(VISAO_GERENCIAL,),
        ),
        ComponenteCusto(
            "Custo de capital de giro",
            capital.custo_financeiro,
            CAMADA_SUSTENTAVEL,
            visoes=(VISAO_GERENCIAL,),
            e_desembolso=False,
        ),
    ]


def main() -> None:  # pragma: no cover - utilitario de demonstracao
    memoria = Memoria(titulo="Lote LC-2026-000001 - papelao misto")
    balanco, aquisicao, transformacao, capital = calcular_lote(memoria)
    componentes = montar_componentes(aquisicao, transformacao, capital)

    estrutura = montar_estrutura(
        componentes, quantidade_vendavel=balanco.quantidade_vendavel
    )

    print("=" * 78)
    print("LOTE LC-2026-000001 | papelao misto | 12.000 kg negociados")
    print("=" * 78)
    print(f"  quantidade aceita ....... {balanco.quantidade_aceita} kg")
    print(f"  quantidade vendavel ..... {balanco.quantidade_vendavel} kg")
    print(f"  rendimento .............. {balanco.rendimento:.2%}")
    print(f"  custo de aquisicao ...... R$ {arredondar(aquisicao.custo_total, 2)}")
    print(f"  custo de transformacao .. R$ {arredondar(transformacao.custo_total, 2)}")
    print(f"  custo de capital ........ R$ {arredondar(capital.custo_financeiro, 2)}")
    print()
    print("  Custo unitario por camada (R$/kg vendavel)")
    for camada in (CAMADA_CAIXA, CAMADA_CONTRIBUICAO, CAMADA_OPERACIONAL, CAMADA_SUSTENTAVEL):
        print(f"    {camada:<14} {arredondar(estrutura.unitario(camada), 4)}")

    print()
    print("=" * 78)
    print("ESCADA DE PRECOS POR REGIME TRIBUTARIO (R$/kg)")
    print("=" * 78)
    print(f"  {'regime':<20}{'r':>10}{'contribuicao':>16}{'sustentavel':>14}{'alvo':>10}")

    for regime in ("LUCRO_REAL", "LUCRO_PRESUMIDO"):
        contexto = ContextoFiscal(
            data_operacao=DATA,
            tipo_operacao="VENDA",
            regime_tributario=regime,
            uf_origem="SP",
            uf_destino="SP",
        )
        deducoes = calcular_deducoes_venda(_regras_por_regime(regime), contexto)
        escada = montar_escada(
            estrutura,
            deducoes_r=deducoes.r_total,
            margem_contribuicao_minima=D("0.05"),
            margem_alvo=D("0.12"),
        )
        status = deducoes.apuracao.status_consolidado
        print(
            f"  {regime:<20}"
            f"{deducoes.r_total:>9.2%} "
            f"{arredondar(escada.preco(CAMADA_CONTRIBUICAO), 4):>15} "
            f"{arredondar(escada.preco(CAMADA_SUSTENTAVEL), 4):>13} "
            f"{arredondar(escada.preco(CAMADA_ALVO), 4):>9}"
            f"   [{status}]"
        )

    print()
    print(
        "  Status PROVISORIA significa: precos validos como estimativa, nao como\n"
        "  cotacao definitiva, ate o responsavel fiscal validar a matriz."
    )

    print()
    print("=" * 78)
    print("ALERTA DE MUDANCA DE FAIXA NO SIMPLES NACIONAL")
    print("=" * 78)
    impacto = simular_mudanca_faixa(
        construir_faixas_simples(),
        rbt12_atual=D("700000"),
        receita_mes_sem_a_venda=D("60000"),
        receita_da_venda=D("40000"),
        anexo="ANEXO_II",
    )
    print(f"  faixa {impacto.faixa_antes} -> {impacto.faixa_depois}")
    print(f"  aliquota efetiva: {impacto.aliquota_antes:.4%} -> {impacto.aliquota_depois:.4%}")
    print(f"  DAS adicional do mes: R$ {arredondar(impacto.das_adicional, 2)}")
    print(f"  aliquota marginal real da venda: {impacto.aliquota_marginal_da_venda:.4%}")
    print(f"  {impacto.alerta}")

    print()
    print("=" * 78)
    print("MEMORIA DE CALCULO (extrato)")
    print("=" * 78)
    print("\n".join(memoria.texto().splitlines()[:24]))
    print(f"  ... {len(memoria.passos)} passos registrados no total")


if __name__ == "__main__":  # pragma: no cover
    main()
