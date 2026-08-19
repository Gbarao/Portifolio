"""Testes do tratamento por regime tributario (secoes 7.7 e 9.4).

E aqui que o modelo se diferencia de uma planilha: a mesma operacao produz
`r` e `C` distintos conforme o enquadramento da empresa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.dominio.excecoes import ParametroInvalidoError
from app.dominio.memoria import Memoria
from app.dominio.precos import calcular_preco
from app.tributario.regimes import (
    calcular_aliquota_efetiva_simples,
    calcular_creditos_compra,
    calcular_deducoes_venda,
    simular_mudanca_faixa,
)
from app.tributario.resolucao import ContextoFiscal
from tests.fixtures_fiscais import (
    faixas_anexo_ii,
    regra_credito_condicionado,
    regras_lucro_presumido,
    regras_lucro_real,
)

DATA = date(2026, 3, 10)


def contexto(regime: str) -> ContextoFiscal:
    return ContextoFiscal(
        data_operacao=DATA,
        tipo_operacao="VENDA",
        regime_tributario=regime,
        uf_origem="SP",
        uf_destino="SP",
    )


# --------------------------------------------------------------------------
# A) Lucro Real
# --------------------------------------------------------------------------
def test_lucro_real_r_contem_pis_e_cofins_mas_nao_irpj_csll():
    """Secao 7.7-A: IRPJ e CSLL incidem sobre o lucro apurado, nao sobre a
    receita. A margem-alvo e, portanto, margem antes desses tributos."""

    deducoes = calcular_deducoes_venda(regras_lucro_real(), contexto("LUCRO_REAL"))

    assert deducoes.r_total == D("0.0925"), "1,65% + 7,6% = 9,25%"
    assert set(deducoes.detalhamento) == {"PIS", "COFINS"}
    assert "IRPJ" not in deducoes.detalhamento

    # O IRPJ foi apurado e permanece visivel, apenas fora de r.
    irpj = deducoes.apuracao.por_tributo("IRPJ")
    assert irpj is not None
    assert irpj.efeito_percentual_sobre_preco == D("0")


def test_lucro_real_credito_da_lei_15394_so_reduz_custo_com_condicao_confirmada():
    """Secao 9.4-1: a lei autoriza credito na aquisicao de residuos por PJ do
    lucro real que os use como materia-prima. E regra condicional."""

    contexto_compra = ContextoFiscal(
        data_operacao=DATA, tipo_operacao="COMPRA", regime_tributario="LUCRO_REAL"
    )
    regras = [regra_credito_condicionado()]

    sem_confirmacao = calcular_creditos_compra(
        regras, contexto_compra, valor_compra=D("100000")
    )
    assert sem_confirmacao.creditos_confirmados == D("0")
    assert sem_confirmacao.creditos_condicionados == D("1650")

    com_confirmacao = calcular_creditos_compra(
        regras,
        contexto_compra,
        valor_compra=D("100000"),
        condicoes_confirmadas={"LR-COMPRA-PIS-CREDITO": True},
    )
    assert com_confirmacao.creditos_confirmados == D("1650")
    assert com_confirmacao.creditos_condicionados == D("0")


# --------------------------------------------------------------------------
# B) Lucro Presumido
# --------------------------------------------------------------------------
def test_lucro_presumido_r_inclui_presuncao_de_irpj_e_csll():
    """Secao 7.7-B: no presumido a presuncao torna IRPJ/CSLL percentuais
    lineares sobre a receita bruta -- deducoes diretas do preco."""

    deducoes = calcular_deducoes_venda(
        regras_lucro_presumido(), contexto("LUCRO_PRESUMIDO")
    )

    # PIS 0,65% + Cofins 3% + IRPJ (8% × 15% = 1,2%) + CSLL (12% × 9% = 1,08%).
    assert deducoes.detalhamento["IRPJ"] == D("0.0120")
    assert deducoes.detalhamento["CSLL"] == D("0.0108")
    assert deducoes.r_total == D("0.0593")


def test_presumido_tem_r_menor_mas_custo_maior_que_o_lucro_real():
    """O confronto que a secao 7.7 pede: o presumido deduz menos da receita,
    mas nao credita nada na compra. A comparacao so faz sentido junta."""

    r_real = calcular_deducoes_venda(regras_lucro_real(), contexto("LUCRO_REAL")).r_total
    r_presumido = calcular_deducoes_venda(
        regras_lucro_presumido(), contexto("LUCRO_PRESUMIDO")
    ).r_total

    assert r_presumido < r_real

    # Mesmo custo de compra bruto; no lucro real ha credito de 9,25%.
    compra = D("100000")
    custo_real = compra * (D("1") - D("0.0925"))
    custo_presumido = compra

    preco_real = calcular_preco(custo_real, r_real, D("0.12"))
    preco_presumido = calcular_preco(custo_presumido, r_presumido, D("0.12"))

    assert preco_presumido > preco_real, (
        "a cumulatividade do presumido encarece o preco apesar do r menor"
    )


# --------------------------------------------------------------------------
# C) Simples Nacional
# --------------------------------------------------------------------------
def test_aliquota_efetiva_do_simples_nao_e_a_nominal():
    """efetiva = (RBT12 × nominal - parcela a deduzir) / RBT12."""

    resultado = calcular_aliquota_efetiva_simples(
        faixas_anexo_ii(), rbt12=D("600000"), anexo="ANEXO_II"
    )

    assert resultado.ordem_faixa == 3
    assert resultado.aliquota_nominal == D("0.10")
    # (600000 × 0,10 - 13860) / 600000 = 7,69%
    assert resultado.aliquota_efetiva == D("0.0769")
    assert resultado.aliquota_efetiva < resultado.aliquota_nominal


def test_simples_segrega_icms_do_das_quando_ha_diferimento_estadual():
    """Secao 9.4-3: sem a segregacao a empresa recolheria dentro do DAS um
    ICMS que a legislacao estadual afastou."""

    memoria = Memoria(titulo="Simples com ICMS diferido")
    resultado = calcular_aliquota_efetiva_simples(
        faixas_anexo_ii(),
        rbt12=D("600000"),
        anexo="ANEXO_II",
        icms_segregado=True,
        memoria=memoria,
    )

    # 7,69% × (1 - 32%) = 5,2292%
    assert resultado.aliquota_efetiva_sem_icms == D("0.052292")
    assert any("icms" in a.lower() for a in memoria.alertas)


def test_venda_que_muda_de_faixa_encarece_todo_o_faturamento_do_mes():
    """Secao 7.7-C, o alerta critico: a aliquota nova alcanca o mes inteiro,
    nao apenas a venda que provocou a mudanca."""

    memoria = Memoria(titulo="Mudanca de faixa")
    impacto = simular_mudanca_faixa(
        faixas_anexo_ii(),
        rbt12_atual=D("700000"),
        receita_mes_sem_a_venda=D("60000"),
        receita_da_venda=D("40000"),
        anexo="ANEXO_II",
        memoria=memoria,
    )

    assert impacto.mudou_de_faixa
    assert impacto.faixa_antes == 3 and impacto.faixa_depois == 4
    assert impacto.aliquota_depois > impacto.aliquota_antes

    # A aliquota marginal real da venda supera a aliquota da faixa anterior:
    # e esse o custo escondido que o vendedor precisa enxergar.
    assert impacto.aliquota_marginal_da_venda > impacto.aliquota_antes
    assert impacto.das_adicional_atribuivel_a_venda > D("0")
    assert impacto.alerta and "faixa" in impacto.alerta.lower()


def test_venda_que_nao_muda_de_faixa_nao_dispara_alerta():
    impacto = simular_mudanca_faixa(
        faixas_anexo_ii(),
        rbt12_atual=D("400000"),
        receita_mes_sem_a_venda=D("30000"),
        receita_da_venda=D("10000"),
        anexo="ANEXO_II",
    )

    assert not impacto.mudou_de_faixa
    assert impacto.alerta is None


def test_rbt12_fora_das_faixas_bloqueia_o_calculo():
    """Acima do teto do Simples nao existe aliquota: o motor recusa em vez de
    extrapolar a ultima faixa."""

    with pytest.raises(ParametroInvalidoError, match="não se enquadra"):
        calcular_aliquota_efetiva_simples(
            faixas_anexo_ii(), rbt12=D("5000000"), anexo="ANEXO_II"
        )
