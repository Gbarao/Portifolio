"""Testes do modelo de dados (Passo 2).

Cobrem o que ja e verificavel sem o motor de calculo: integridade do schema,
fidelidade ao modelo conceitual da secao 10 e as invariantes que a estrutura
precisa sustentar antes de o motor existir.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import Base, LoteCompra, Material, RegraTributaria
from app.models.enums import StatusRegraFiscal
from app.seeds.demo import popular

# Entidades exigidas pelo modelo conceitual da secao 10.
ENTIDADES_ESPECIFICACAO = {
    "empresa_parametro",
    "material",
    "parceiro",
    "contrato_tabela",
    "lote_compra",
    "evento_balanca",
    "evento_qualidade",
    "evento_processo",
    "lote_saida",
    "rejeito_perda",
    "empregado_custo",
    "veiculo_custo",
    "maquina_custo",
    "centro_custo",
    "atividade_taxa",
    "regra_tributaria",
    "cotacao_venda",
    "pedido_venda",
    "evento_frete",
    "fechamento_mensal",
    "auditoria",
}


def test_todas_entidades_da_especificacao_existem():
    faltando = ENTIDADES_ESPECIFICACAO - set(Base.metadata.tables)
    assert not faltando, f"entidades ausentes no schema: {sorted(faltando)}"


def test_valores_monetarios_nunca_usam_ponto_flutuante():
    """Reprodutibilidade da memoria de calculo depende de aritmetica decimal."""

    for tabela in Base.metadata.tables.values():
        for coluna in tabela.columns:
            tipo = coluna.type.__class__.__name__
            assert tipo != "Float", f"{tabela.name}.{coluna.name} usa Float"


def test_registros_financeiros_tem_competencia_e_caixa():
    """Secao 10: competencia move resultado, caixa move capital de giro."""

    for nome in ("lote_compra", "movimento_estoque"):
        colunas = set(Base.metadata.tables[nome].columns.keys())
        assert {"data_competencia", "data_caixa"} <= colunas


def test_regra_tributaria_tem_chaves_minimas_da_secao_9_2():
    colunas = set(Base.metadata.tables["regra_tributaria"].columns.keys())
    minimas = {
        "regime_tributario",
        "tipo_operacao",
        "tributo",
        "ncm",
        "cfop",
        "cst_csosn",
        "uf_origem",
        "uf_destino",
        "natureza_parceiro",
        "regime_parceiro",
        "tratamento",
        "recuperabilidade",
        "vigencia_inicio",
        "vigencia_fim",
        "fundamento_legal",
        "status",
    }
    assert minimas <= colunas


def test_seed_popula_base_completa(sessao):
    dados = popular(sessao)
    sessao.commit()

    assert len(dados["unidades"]) == 3, "um regime tributario por empresa"
    assert sessao.scalar(select(Material).where(Material.codigo == "MP-PAPELAO-MISTO"))
    assert len(dados["faixas"]) == 12, "6 faixas por anexo, Anexos I e II"


def test_nenhuma_regra_de_seed_nasce_validada(sessao):
    """Secao 9.1: so entra em producao regra validada pelo responsavel fiscal.

    Dado de demonstracao jamais pode se passar por parametro aprovado.
    """

    popular(sessao)
    sessao.commit()

    regras = sessao.scalars(select(RegraTributaria)).all()
    assert regras
    assert all(r.status == StatusRegraFiscal.PROVISORIA for r in regras)
    assert all(r.fundamento_legal for r in regras), "toda regra cita fundamento"


def test_lote_de_exemplo_fecha_o_balanco_de_massa(sessao):
    """Secao 7.1: aceita = vendavel + rejeito + perdas."""

    popular(sessao)
    sessao.commit()

    lote = sessao.scalar(select(LoteCompra).where(LoteCompra.codigo == "LC-2026-000001"))
    recusado = sum(e.quantidade_recusada_kg for e in lote.eventos_qualidade)
    liquido = sum(e.peso_liquido_kg for e in lote.eventos_balanca)
    aceita = liquido - recusado

    vendavel = sum(s.quantidade_kg for s in lote.saidas)
    perdas = sum(p.quantidade_kg for p in lote.perdas)

    assert aceita == Decimal("11600")
    assert vendavel + perdas == aceita
    assert vendavel / aceita == Decimal("0.9"), "rendimento de 90%"


def test_credito_condicionado_nao_e_marcado_como_elegivel(sessao):
    """Secao 6.1: credito condicionado nao pode reduzir custo automaticamente."""

    popular(sessao)
    sessao.commit()

    regra = sessao.scalar(
        select(RegraTributaria).where(RegraTributaria.codigo == "LR-COMPRA-PIS-CREDITO")
    )
    assert regra.requer_confirmacao_condicao is True
    assert regra.condicao_descricao
    assert "15.394" in regra.fundamento_legal


def test_irpj_csll_do_lucro_real_ficam_fora_das_deducoes(sessao):
    """Secao 7.7-A: IRPJ/CSLL incidem sobre o lucro, nao sobre a receita."""

    popular(sessao)
    sessao.commit()

    for codigo in ("LR-IRPJ-LUCRO", "LR-CSLL-LUCRO"):
        regra = sessao.scalar(
            select(RegraTributaria).where(RegraTributaria.codigo == codigo)
        )
        assert regra.incide_sobre_lucro is True
        assert regra.compoe_deducao_venda is False


def test_irpj_csll_do_lucro_presumido_integram_as_deducoes(sessao):
    """Secao 7.7-B: no presumido a presuncao age como deducao linear."""

    popular(sessao)
    sessao.commit()

    regra = sessao.scalar(
        select(RegraTributaria).where(
            RegraTributaria.codigo == "LP-VENDA-IRPJ-PRESUMIDO"
        )
    )
    assert regra.compoe_deducao_venda is True
    assert regra.percentual_presuncao_base == Decimal("0.08")
    # Efeito em r = presuncao x aliquota = 8% x 15% = 1,2%.
    assert regra.percentual_presuncao_base * regra.aliquota == Decimal("0.0120")


def test_simples_nao_gera_credito_na_compra(sessao):
    """Secao 7.7-C: nota de compra inteira e custo, sem credito."""

    popular(sessao)
    sessao.commit()

    regra = sessao.scalar(
        select(RegraTributaria).where(RegraTributaria.codigo == "SN-COMPRA-SEM-CREDITO")
    )
    assert regra.gera_credito_compra is False
    assert regra.compoe_custo_nao_recuperavel is True


def test_faixas_do_simples_cobrem_a_receita_sem_lacuna(sessao):
    """A simulacao de mudanca de faixa exige faixas continuas."""

    dados = popular(sessao)
    sessao.commit()

    for anexo in {f.anexo for f in dados["faixas"]}:
        faixas = sorted(
            (f for f in dados["faixas"] if f.anexo == anexo),
            key=lambda f: f.ordem_faixa,
        )
        for anterior, seguinte in zip(faixas, faixas[1:]):
            lacuna = seguinte.rbt12_inicio - anterior.rbt12_fim
            assert lacuna == Decimal("0.01"), (
                f"{anexo} tem lacuna entre as faixas "
                f"{anterior.ordem_faixa} e {seguinte.ordem_faixa}"
            )


def test_chave_estrangeira_invalida_e_rejeitada(sessao):
    """Evento orfao nao pode existir: o lote e a unidade de rastreamento."""

    import uuid

    from app.models import EventoBalanca

    sessao.add(
        EventoBalanca(
            lote_id=uuid.uuid4(),
            peso_bruto_kg=Decimal("1000"),
            tara_kg=Decimal("100"),
            peso_liquido_kg=Decimal("900"),
            data_hora=__import__("datetime").datetime(2026, 3, 1, 8, 0),
        )
    )
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_toda_tabela_versionada_tem_vigencia():
    """Parametro sem vigencia nao permite reproduzir cotacao antiga."""

    versionadas = [
        "empresa_parametro",
        "contrato_tabela",
        "empregado_custo",
        "veiculo_custo",
        "maquina_custo",
        "imovel_custo",
        "atividade_taxa",
        "despesa_estrutural",
        "regra_tributaria",
        "faixa_simples_nacional",
    ]
    for nome in versionadas:
        colunas = set(Base.metadata.tables[nome].columns.keys())
        assert {"vigencia_inicio", "vigencia_fim", "versao"} <= colunas, nome


def test_indices_de_resolucao_fiscal_existem(engine):
    """A resolucao de regra roda a cada linha de cotacao: precisa de indice."""

    indices = {i["name"] for i in inspect(engine).get_indexes("regra_tributaria")}
    assert "ix_regra_tributaria_resolucao" in indices
