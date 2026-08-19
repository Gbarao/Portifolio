"""Os 11 casos de aceitacao da secao 17.

Sao criterios de implantacao, nao testes unitarios: cada um verifica um
comportamento que a especificacao exige antes de o sistema entrar em producao.
O nome de cada teste cita o numero do caso correspondente.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.aplicacao.cotacao import (
    PremissasCotacao,
    gerar_versao,
    reproduzir_preco,
    revisar,
)
from app.dominio.abc import (
    ConsumoAtividade,
    LancamentoDireto,
    TaxaAtividade,
    calcular_custo_transformacao,
    calcular_ociosidade,
)
from app.dominio.aquisicao import EntradasAquisicao, calcular_custo_aquisicao
from app.dominio.camadas import (
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
    ComponenteCusto,
)
from app.dominio.capital import CicloFinanceiro, calcular_custo_capital
from app.dominio.conjuntos import ProdutoConjunto, ratear_por_vrl
from app.dominio.excecoes import DuplaContagemError
from app.dominio.massa import calcular_balanco
from app.dominio.memoria import Memoria
from app.dominio.reconciliacao import ResultadoLote, reconciliar_periodo
from app.dominio.recursos import FichaVeiculo, calcular_custo_viagem
from app.tributario.calculo import aplicar_regra
from app.tributario.regimes import calcular_deducoes_venda
from app.tributario.resolucao import ContextoFiscal
from tests.fixtures_fiscais import (
    regra_credito_condicionado,
    regra_credito_vedado,
    regra_vencida,
    regras_lucro_real,
)

DATA = date(2026, 3, 10)


def contexto_venda(regime: str = "LUCRO_REAL") -> ContextoFiscal:
    return ContextoFiscal(
        data_operacao=DATA,
        tipo_operacao="VENDA",
        regime_tributario=regime,
        uf_origem="SP",
        uf_destino="SP",
    )


# --------------------------------------------------------------------------
# Caso 1
# --------------------------------------------------------------------------
def test_caso_01_perda_de_10_por_cento_transfere_custo_para_a_quantidade_vendavel():
    """Um lote com 10% de perda transfere o custo para 90% da quantidade
    vendavel, sem perder o registro da perda."""

    memoria = Memoria(titulo="Caso 1")
    balanco = calcular_balanco(
        peso_bruto=D("11000"),
        tara=D("1000"),
        quantidade_vendavel=D("9000"),
        perda_normal=D("1000"),
        memoria=memoria,
    )

    assert balanco.quantidade_aceita == D("10000")
    assert balanco.rendimento == D("0.9")
    # A perda continua registrada, nao foi absorvida silenciosamente.
    assert balanco.perda_normal == D("1000")

    custo = calcular_custo_aquisicao(
        EntradasAquisicao(preco_bruto=D("9000")),
        quantidade_aceita=balanco.quantidade_aceita,
        quantidade_vendavel=balanco.quantidade_vendavel,
        memoria=memoria,
    )

    assert custo.custo_por_kg_aceito == D("0.9")
    # O custo por kg vendavel absorve a perda: 9000 / 9000 = 1,00.
    assert custo.custo_por_kg_vendavel == D("1")
    # E a memoria registra os dois, para que a diferenca seja auditavel.
    assert memoria.resultado_de("Custo por kg vendável") == D("1")


# --------------------------------------------------------------------------
# Caso 2
# --------------------------------------------------------------------------
def test_caso_02_dois_produtos_de_saida_fecham_100_por_cento_do_custo():
    """Um lote com dois produtos de saida reparte o custo conjunto pelo metodo
    aprovado e fecha 100% do custo."""

    custo_conjunto = D("10000")
    produtos = [
        ProdutoConjunto(
            codigo="PET-CRISTAL",
            quantidade=D("5500"),
            preco_estimado_venda=D("2.20"),
            gastos_posteriores=D("0.05"),
        ),
        ProdutoConjunto(
            codigo="PET-COLORIDO",
            quantidade=D("3000"),
            preco_estimado_venda=D("1.40"),
            gastos_posteriores=D("0.04"),
        ),
    ]

    rateios = ratear_por_vrl(custo_conjunto, produtos)

    assert sum(r.custo_atribuido for r in rateios) == custo_conjunto
    assert sum(r.fator for r in rateios) == pytest.approx(D("1"), abs=D("0.0000001"))
    # O produto de maior VRL recebe a maior parcela.
    cristal = next(r for r in rateios if r.codigo == "PET-CRISTAL")
    colorido = next(r for r in rateios if r.codigo == "PET-COLORIDO")
    assert cristal.custo_atribuido > colorido.custo_atribuido


# --------------------------------------------------------------------------
# Caso 3
# --------------------------------------------------------------------------
def test_caso_03_credito_vedado_nao_reduz_custo_e_condicionado_gera_alerta():
    """Um credito fiscal vedado nao pode reduzir o custo; um credito
    condicionado deve gerar alerta."""

    contexto_compra = ContextoFiscal(
        data_operacao=DATA, tipo_operacao="COMPRA", regime_tributario="SIMPLES_NACIONAL"
    )

    vedado = aplicar_regra(
        regra_credito_vedado(), base_bruta=D("10000"), data_operacao=DATA
    )
    assert vedado.valor_recuperavel == D("0"), "credito vedado nao pode ser recuperado"
    assert "vedado" in (vedado.alerta or "").lower()

    condicionado = aplicar_regra(
        regra_credito_condicionado(),
        base_bruta=D("10000"),
        data_operacao=DATA,
        condicao_confirmada=False,
    )
    assert condicionado.credito_entrada_relacionado == D("165")
    assert condicionado.valor_recuperavel == D("0")
    assert "condicionado" in (condicionado.alerta or "").lower()

    # Com a condicao confirmada, o mesmo credito passa a ser aproveitavel.
    confirmado = aplicar_regra(
        regra_credito_condicionado(),
        base_bruta=D("10000"),
        data_operacao=DATA,
        condicao_confirmada=True,
    )
    assert confirmado.valor_recuperavel == D("165")
    assert contexto_compra.tipo_operacao == "COMPRA"


# --------------------------------------------------------------------------
# Caso 4
# --------------------------------------------------------------------------
def test_caso_04_regra_fora_de_vigencia_impede_cotacao_definitiva():
    """Uma regra fiscal fora da vigencia impede cotacao definitiva."""

    regras = regras_lucro_real() + [regra_vencida()]
    deducoes = calcular_deducoes_venda(regras, contexto_venda())

    assert not deducoes.permite_cotacao_definitiva
    assert deducoes.apuracao.status_consolidado == "VENCIDA"
    assert any("vigência" in a.lower() for a in deducoes.alertas)
    # A aliquota da regra vencida nao entrou em r.
    assert "ICMS" not in deducoes.detalhamento


# --------------------------------------------------------------------------
# Caso 5
# --------------------------------------------------------------------------
def test_caso_05_queda_de_volume_gera_ociosidade_sem_inflar_a_taxa():
    """Uma queda de volume abaixo da capacidade pratica gera ociosidade
    separada, sem inflar automaticamente a taxa-padrao."""

    taxa = TaxaAtividade(
        codigo="ATV-TRI",
        nome="Triagem",
        direcionador="HORA_MAO_DE_OBRA",
        pool_custo=D("27600"),
        capacidade_pratica=D("1200"),
    )

    assert taxa.taxa == D("23")

    ociosidade = calcular_ociosidade(taxa, utilizacao_real=D("900"))

    # A taxa nao mudou: continua pool / capacidade pratica.
    assert taxa.taxa == D("23")
    assert ociosidade.capacidade_ociosa == D("300")
    assert ociosidade.custo_ociosidade == D("6900")
    assert ociosidade.percentual_ocupacao == D("0.75")

    # O custo do lote usa a taxa original, nao a inflada pelo volume menor.
    custo = calcular_custo_transformacao(
        [ConsumoAtividade("ATV-TRI", D("6"))], {"ATV-TRI": taxa}
    )
    assert custo.custo_total == D("138")


# --------------------------------------------------------------------------
# Caso 6
# --------------------------------------------------------------------------
def test_caso_06_viagem_com_retorno_vazio_inclui_todos_os_quilometros():
    """Uma viagem com retorno vazio deve incluir todos os quilometros."""

    ficha = FichaVeiculo(
        capacidade_util_kg=D("14000"),
        km_praticos_mes=D("7000"),
        horas_praticas_mes=D("176"),
        depreciacao_ou_arrendamento_mensal=D("6500"),
        combustivel_por_km=D("1.85"),
        pneus_por_km=D("0.22"),
        manutencao_variavel_por_km=D("0.38"),
        lubrificantes_consumiveis_por_km=D("0.07"),
        custo_por_hora_operacao=D("18"),
    )

    memoria = Memoria(titulo="Caso 6")
    viagem = calcular_custo_viagem(
        ficha,
        km_carregado=D("120"),
        km_vazio=D("120"),
        horas_totais=D("6"),
        carga_util_kg=D("12000"),
        pedagio=D("48"),
        memoria=memoria,
    )

    assert viagem.km_totais == D("240"), "km vazio conta integralmente"
    # Custo variavel: 2,52/km × 240 km.
    assert viagem.custo_variavel == D("604.80")
    # O retorno vazio responde por metade do custo variavel.
    assert viagem.custo_km_vazio == D("302.40")
    assert any("vazio" in a.lower() for a in memoria.alertas)


# --------------------------------------------------------------------------
# Caso 7
# --------------------------------------------------------------------------
def test_caso_07_prazo_maior_reflete_capital_de_giro_adicional():
    """Uma cotacao com prazo maior deve refletir capital de giro adicional."""

    capital = D("100000")
    taxa_anual = D("0.18")

    curto = calcular_custo_capital(
        capital_comprometido=capital,
        ciclo=CicloFinanceiro(dias_estoque=10, dias_recebimento=30, dias_pagamento=7),
        taxa_anual=taxa_anual,
    )
    longo = calcular_custo_capital(
        capital_comprometido=capital,
        ciclo=CicloFinanceiro(dias_estoque=10, dias_recebimento=60, dias_pagamento=7),
        taxa_anual=taxa_anual,
    )

    assert curto.dias_comprometidos == 33
    assert longo.dias_comprometidos == 63
    assert longo.custo_financeiro > curto.custo_financeiro
    # Prazo quase dobrado quase dobra o custo financeiro.
    assert longo.custo_financeiro / curto.custo_financeiro > D("1.8")


# --------------------------------------------------------------------------
# Caso 8
# --------------------------------------------------------------------------
def test_caso_08_mesmo_custo_nao_aparece_na_taxa_e_como_lancamento_direto():
    """O mesmo custo nao pode aparecer simultaneamente na taxa de atividade e
    como lancamento direto."""

    taxa = TaxaAtividade(
        codigo="ATV-PRE",
        nome="Prensagem",
        direcionador="HORA_MAQUINA",
        pool_custo=D("6300"),
        capacidade_pratica=D("280"),
    )
    consumos = [ConsumoAtividade("ATV-PRE", D("2.5"))]

    with pytest.raises(DuplaContagemError, match="ATV-PRE"):
        calcular_custo_transformacao(
            consumos,
            {"ATV-PRE": taxa},
            lancamentos_diretos=[
                LancamentoDireto(
                    descricao="Manutencao da prensa",
                    valor=D("500"),
                    atividade_de_origem="ATV-PRE",
                )
            ],
        )

    # Um gasto genuinamente exclusivo do lote passa normalmente.
    resultado = calcular_custo_transformacao(
        consumos,
        {"ATV-PRE": taxa},
        lancamentos_diretos=[
            LancamentoDireto(descricao="Analise laboratorial do lote", valor=D("500"))
        ],
    )
    assert resultado.custos_diretos == D("500")


# --------------------------------------------------------------------------
# Caso 9
# --------------------------------------------------------------------------
def test_caso_09_soma_dos_lotes_reconcilia_com_o_resultado_mensal():
    """A soma dos resultados por lote deve reconciliar com o resultado mensal
    dentro da tolerancia aprovada."""

    lotes = [
        ResultadoLote(codigo="LC-1", receita=D("50000"), custo_total=D("42000")),
        ResultadoLote(codigo="LC-2", receita=D("38000"), custo_total=D("31000")),
        ResultadoLote(codigo="LC-3", receita=D("61000"), custo_total=D("52000")),
    ]
    # 8000 + 7000 + 9000 = 24000, menos ociosidade e perda anormal.
    reconciliacao = reconciliar_periodo(
        lotes,
        resultado_do_periodo=D("15100"),
        custo_ociosidade=D("6900"),
        perdas_anormais=D("2000"),
        tolerancia=D("0.01"),
    )

    assert reconciliacao.soma_dos_lotes == D("24000")
    assert reconciliacao.dentro_da_tolerancia
    assert reconciliacao.divergencia == D("0")

    # Ociosidade nao rateada nos lotes: continua visivel como item do periodo.
    assert reconciliacao.itens_nao_atribuidos["custo_ociosidade"] == D("6900")

    fora = reconciliar_periodo(
        lotes,
        resultado_do_periodo=D("21000"),
        custo_ociosidade=D("6900"),
        perdas_anormais=D("2000"),
        tolerancia=D("0.01"),
    )
    assert not fora.dentro_da_tolerancia
    assert fora.alertas


# --------------------------------------------------------------------------
# Casos 10 e 11
# --------------------------------------------------------------------------
def premissas_base() -> PremissasCotacao:
    return PremissasCotacao(
        data_referencia=DATA,
        quantidade_kg=D("10000"),
        margem_alvo=D("0.12"),
        margem_contribuicao_minima=D("0.05"),
        componentes_custo=(
            # Pagar o fornecedor e desembolso incremental: entra ja no preco de caixa.
            ComponenteCusto("Aquisicao", D("5000"), CAMADA_CAIXA),
            ComponenteCusto("Transformacao variavel", D("800"), CAMADA_CONTRIBUICAO),
            ComponenteCusto("Transformacao fixa", D("1200"), CAMADA_OPERACIONAL),
            ComponenteCusto(
                "Despesas estruturais",
                D("900"),
                CAMADA_SUSTENTAVEL,
                visoes=("GERENCIAL_COMPLETO",),
            ),
        ),
    )


def test_caso_10_alteracao_de_premissa_gera_nova_versao_e_preserva_a_anterior():
    """Alteracao de premissa deve gerar nova versao e preservar a memoria
    anterior."""

    regras = regras_lucro_real()
    contexto = contexto_venda()

    v1 = gerar_versao(premissas_base(), regras_fiscais=regras, contexto_fiscal=contexto)
    preco_v1 = v1.escada.preco("ALVO")
    memoria_v1 = v1.memoria.exportar()

    v2 = revisar(
        v1,
        regras_fiscais=regras,
        contexto_fiscal=contexto,
        margem_alvo=D("0.18"),
    )

    assert v2.numero == 2
    assert v2.escada.preco("ALVO") > preco_v1, "margem maior eleva o preco"

    # A versao anterior permanece intacta -- objeto e memoria.
    assert v1.numero == 1
    assert v1.premissas.margem_alvo == D("0.12")
    assert v1.escada.preco("ALVO") == preco_v1
    assert v1.memoria.exportar() == memoria_v1


def test_caso_11_usuario_reproduz_o_preco_a_partir_do_que_foi_exportado():
    """O usuario deve conseguir reproduzir o preco a partir dos dados e
    formulas exportados."""

    versao = gerar_versao(
        premissas_base(),
        regras_fiscais=regras_lucro_real(),
        contexto_fiscal=contexto_venda(),
    )
    exportacao = versao.exportar()

    for camada in ("SUSTENTAVEL", "ALVO", "CONTRIBUICAO"):
        reproduzido = reproduzir_preco(exportacao, camada)
        assert reproduzido == versao.escada.preco(camada), (
            f"preco da camada {camada} nao pode ser reproduzido pela exportacao"
        )

    # A memoria exportada traz formula e entradas de cada passo.
    passos = exportacao["memoria_calculo"]["passos"]
    assert passos
    assert all(p["formula"] and p["entradas"] for p in passos)
    assert any("P = C / [(1 - r) × (1 - m)]" in p["formula"] for p in passos)
