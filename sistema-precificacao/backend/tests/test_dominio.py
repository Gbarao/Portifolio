"""Testes do motor de custeio: massa, custos, camadas, escada e alcadas."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.dominio.abc import TaxaAtividade, calcular_taxa
from app.dominio.camadas import (
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
    VISAO_CONTABIL,
    VISAO_GERENCIAL,
    ComponenteCusto,
    montar_estrutura,
)
from app.dominio.conjuntos import ProdutoConjunto, creditar_subproduto, ratear_por_vrl
from app.dominio.excecoes import (
    DenominadorZeroError,
    MassaInconsistenteError,
    ParametroInvalidoError,
)
from app.dominio.massa import calcular_balanco
from app.dominio.memoria import Memoria
from app.dominio.precos import (
    CAMADA_ALVO,
    calcular_preco,
    calcular_preco_maximo_compra,
    montar_escada,
)
from app.dominio.recursos import (
    FichaEmpregado,
    FichaMaquina,
    calcular_custo_empregado,
    calcular_custo_maquina,
)
from app.dominio.unidades import dividir, taxa_diaria_equivalente


# --------------------------------------------------------------------------
# Balanco de massa
# --------------------------------------------------------------------------
def test_balanco_fora_da_tolerancia_bloqueia_o_encerramento():
    """Secao 7.1: divergencia acima da tolerancia bloqueia o lote."""

    with pytest.raises(MassaInconsistenteError, match="tolerancia"):
        calcular_balanco(
            peso_bruto=D("10000"),
            tara=D("0"),
            quantidade_vendavel=D("8000"),
            quantidade_rejeito=D("500"),
            perda_normal=D("200"),
            tolerancia=D("0.02"),
        )


def test_balanco_permite_encerrar_com_excecao_aprovada():
    """A excecao existe, mas exige escolha explicita -- nao e o padrao."""

    balanco = calcular_balanco(
        peso_bruto=D("10000"),
        tara=D("0"),
        quantidade_vendavel=D("8000"),
        quantidade_rejeito=D("500"),
        perda_normal=D("200"),
        tolerancia=D("0.02"),
        bloquear_fora_da_tolerancia=False,
    )
    assert not balanco.dentro_da_tolerancia
    assert balanco.diferenca_nao_explicada == D("1300")


def test_perda_anormal_fica_separada_da_perda_normal():
    """Secao 6.6: perda anormal e desvio do periodo, nao custo-padrao."""

    balanco = calcular_balanco(
        peso_bruto=D("10000"),
        tara=D("0"),
        quantidade_vendavel=D("9000"),
        perda_normal=D("600"),
        perda_anormal=D("400"),
    )
    assert balanco.perda_normal == D("600")
    assert balanco.perda_anormal == D("400")
    assert balanco.perda_total == D("1000")


def test_lote_sem_quantidade_aceita_bloqueia_em_vez_de_dividir_por_zero():
    with pytest.raises(DenominadorZeroError):
        calcular_balanco(
            peso_bruto=D("1000"), tara=D("1000"), quantidade_vendavel=D("0")
        )


# --------------------------------------------------------------------------
# Recursos
# --------------------------------------------------------------------------
def test_custo_da_hora_produtiva_e_maior_que_o_da_hora_paga():
    """Secao 6.2: usar horas pagas como se fossem produtivas subestima o custo."""

    ficha = FichaEmpregado(
        salario_base=D("2200"),
        encargos_patronais=D("620"),
        beneficios=D("480"),
        horas_pagas_mes=D("176"),
        horas_produtivas_praticas_mes=D("150"),
    )
    custo = calcular_custo_empregado(ficha)

    assert custo.custo_mensal_integral == D("3300")
    assert custo.custo_hora_produtiva == D("22")
    assert custo.custo_hora_produtiva > custo.custo_hora_paga
    assert custo.horas_nao_produtivas == D("26")


def test_hora_maquina_usa_capacidade_pratica_e_nao_a_teorica():
    """Secao 6.4: a capacidade pratica ja desconta setup e manutencao."""

    ficha = FichaMaquina(
        horas_praticas_mes=D("280"),
        depreciacao_mensal=D("3800"),
        custo_capital_mensal=D("1200"),
        energia_kwh_por_hora=D("20"),
        custo_energia_por_kwh=D("0.80"),
    )
    custo = calcular_custo_maquina(ficha, horas_efetivas=D("10"))

    # Fixo: 5000 / 280 = 17,857.../hora; variavel: 20 × 0,80 = 16,00/hora.
    assert custo.custo_variavel_por_hora == D("16")
    assert custo.custo_fixo_por_hora == dividir(D("5000"), D("280"))
    assert custo.custo_do_uso == custo.custo_total_por_hora * D("10")


# --------------------------------------------------------------------------
# ABC
# --------------------------------------------------------------------------
def test_taxa_de_atividade_com_capacidade_zero_e_recusada():
    with pytest.raises(DenominadorZeroError, match="ATV-X"):
        calcular_taxa(D("1000"), D("0"), codigo="ATV-X")


def test_ociosidade_considera_apenas_a_parcela_fixa_quando_informada():
    """Pool com parte variavel nao gera ociosidade sobre o total: insumo nao
    consumido nao vira custo."""

    from app.dominio.abc import calcular_ociosidade

    taxa = TaxaAtividade(
        codigo="ATV-PRE",
        nome="Prensagem",
        direcionador="HORA_MAQUINA",
        pool_custo=D("6300"),
        capacidade_pratica=D("280"),
        percentual_fixo=D("0.70"),
    )
    ociosidade = calcular_ociosidade(taxa, utilizacao_real=D("200"))

    # (280 - 200) × (22,50 × 0,70) = 80 × 15,75 = 1260.
    assert ociosidade.custo_ociosidade == D("1260.00")


# --------------------------------------------------------------------------
# Produtos conjuntos
# --------------------------------------------------------------------------
def test_receita_de_subproduto_so_reduz_custo_com_politica_aprovada():
    """Secao 7.4 e regra 13: receita e credito de custo nunca coexistem."""

    memoria = Memoria(titulo="Subproduto")
    sem_politica = creditar_subproduto(
        D("10000"), D("800"), politica_aprovada=False, memoria=memoria
    )
    assert sem_politica == D("10000")
    assert any("nao aprovada" in a.lower() for a in memoria.alertas)

    com_politica = creditar_subproduto(D("10000"), D("800"), politica_aprovada=True)
    assert com_politica == D("9200")


def test_rateio_recusa_vrl_total_nao_positivo():
    """Preco estimado abaixo dos gastos posteriores invalida o criterio."""

    with pytest.raises(ParametroInvalidoError, match="realizaveis liquidos"):
        ratear_por_vrl(
            D("1000"),
            [
                ProdutoConjunto(
                    codigo="X",
                    quantidade=D("100"),
                    preco_estimado_venda=D("0.10"),
                    gastos_posteriores=D("0.50"),
                )
            ],
        )


# --------------------------------------------------------------------------
# Camadas e visoes
# --------------------------------------------------------------------------
def componentes_exemplo() -> list[ComponenteCusto]:
    return [
        ComponenteCusto("Aquisicao", D("5000"), CAMADA_CAIXA),
        ComponenteCusto("Transformacao variavel", D("800"), CAMADA_CONTRIBUICAO),
        ComponenteCusto(
            "Depreciacao alocada",
            D("1200"),
            CAMADA_OPERACIONAL,
            e_desembolso=False,
        ),
        ComponenteCusto(
            "Despesas administrativas",
            D("900"),
            CAMADA_SUSTENTAVEL,
            visoes=(VISAO_GERENCIAL,),
            e_desembolso=True,
            e_relevante_para_decisao=False,
        ),
    ]


def test_camadas_sao_cumulativas():
    estrutura = montar_estrutura(
        componentes_exemplo(), quantidade_vendavel=D("10000")
    )

    assert estrutura.total(CAMADA_CAIXA) == D("5000")
    assert estrutura.total(CAMADA_CONTRIBUICAO) == D("5800")
    assert estrutura.total(CAMADA_OPERACIONAL) == D("7000")
    assert estrutura.total(CAMADA_SUSTENTAVEL) == D("7900")


def test_preco_de_caixa_ignora_itens_que_nao_saem_do_caixa():
    """Depreciacao nao e desembolso: nao entra na camada de caixa."""

    estrutura = montar_estrutura(
        componentes_exemplo(), quantidade_vendavel=D("10000")
    )
    assert "Depreciacao alocada" not in estrutura.camadas[CAMADA_CAIXA].componentes


def test_visao_contabil_nao_recebe_despesa_administrativa():
    """Secao 6.7: despesa de estrutura nao contamina o custo do estoque."""

    estrutura = montar_estrutura(
        componentes_exemplo(), quantidade_vendavel=D("10000")
    )
    assert estrutura.visoes[VISAO_CONTABIL] == D("7000")
    assert estrutura.visoes[VISAO_GERENCIAL] == D("7900")


# --------------------------------------------------------------------------
# Precos
# --------------------------------------------------------------------------
def test_formula_de_preco_reproduz_a_margem_alvo():
    """P = C / [(1-r)(1-m)] tem que devolver exatamente a margem pedida."""

    preco = calcular_preco(D("1.00"), D("0.0925"), D("0.12"))
    receita_liquida = preco * (D("1") - D("0.0925"))
    margem = (receita_liquida - D("1.00")) / receita_liquida

    assert round(margem, 6) == D("0.120000")


def test_deducoes_de_cem_por_cento_sao_recusadas():
    with pytest.raises(ParametroInvalidoError, match="receita liquida"):
        calcular_preco(D("1.00"), D("1.00"), D("0.10"))


def test_escada_ordena_os_precos_do_caixa_ao_alvo():
    estrutura = montar_estrutura(
        componentes_exemplo(), quantidade_vendavel=D("10000")
    )
    escada = montar_escada(
        estrutura,
        deducoes_r=D("0.0925"),
        margem_contribuicao_minima=D("0.05"),
        margem_alvo=D("0.12"),
    )

    precos = [
        escada.preco(CAMADA_CAIXA),
        escada.preco(CAMADA_CONTRIBUICAO),
        escada.preco(CAMADA_OPERACIONAL),
        escada.preco(CAMADA_SUSTENTAVEL),
        escada.preco(CAMADA_ALVO),
    ]
    assert precos == sorted(precos), "a escada tem que ser monotonica"
    # Cada degrau declara sua finalidade -- nenhum preco circula sem rotulo.
    assert all(d.finalidade for d in escada.degraus.values())


def test_proposta_abaixo_do_sustentavel_exige_alcada_e_mostra_a_concessao():
    """Secao 13.2: alcada por margem e risco, nao por desconto nominal."""

    estrutura = montar_estrutura(
        componentes_exemplo(), quantidade_vendavel=D("10000")
    )
    escada = montar_escada(
        estrutura,
        deducoes_r=D("0.0925"),
        margem_contribuicao_minima=D("0.05"),
        margem_alvo=D("0.12"),
    )

    sustentavel = escada.preco(CAMADA_SUSTENTAVEL)
    avaliacao = escada.avaliar_proposta(sustentavel * D("0.95"))

    assert avaliacao.faixa == "ENTRE_SUSTENTAVEL_E_CONTRIBUICAO"
    assert "Controladoria" in avaliacao.alcada_necessaria
    assert avaliacao.valor_concessao > D("0")
    assert not avaliacao.bloqueado


def test_preco_que_nao_cobre_o_caixa_e_bloqueado():
    estrutura = montar_estrutura(
        componentes_exemplo(), quantidade_vendavel=D("10000")
    )
    escada = montar_escada(
        estrutura,
        deducoes_r=D("0.0925"),
        margem_contribuicao_minima=D("0.05"),
        margem_alvo=D("0.12"),
    )

    avaliacao = escada.avaliar_proposta(escada.preco(CAMADA_CAIXA) * D("0.5"))
    assert avaliacao.bloqueado
    assert avaliacao.faixa == "CAIXA_INCREMENTAL_NEGATIVO"


def test_preco_maximo_de_compra_fecha_com_a_margem_alvo():
    """Secao 14: com preco de venda dado pelo mercado, a decisao e a compra."""

    resultado = calcular_preco_maximo_compra(
        preco_venda_unitario=D("0.95"),
        quantidade_vendavel=D("9000"),
        deducoes_r=D("0.0925"),
        demais_custos=D("2000"),
        margem_alvo=D("0.12"),
        quantidade_aceita_esperada=D("10000"),
    )

    receita_liquida = D("0.95") * D("9000") * (D("1") - D("0.0925"))
    esperado = (receita_liquida - D("2000") - receita_liquida * D("0.12")) / D("10000")

    assert resultado.receita_liquida_total == receita_liquida
    assert resultado.preco_maximo_unitario == esperado


# --------------------------------------------------------------------------
# Unidades
# --------------------------------------------------------------------------
def test_taxa_diaria_capitaliza_em_vez_de_dividir_por_365():
    """Juros simples subestimariam o custo do capital no ciclo financeiro."""

    diaria = taxa_diaria_equivalente(D("0.18"))
    simples = D("0.18") / D("365")

    assert diaria < simples
    assert round((D("1") + diaria) ** D("365") - D("1"), 8) == D("0.18000000")
