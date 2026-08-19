"""Schemas do motor tributario."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import Field

from app.api.schemas.comum import Base, ContextoFiscalIn, MemoriaOut


class RegraTributariaIn(Base):
    codigo: str
    descricao: str
    tipo_operacao: str
    tributo: str
    regime_tributario: str | None = None
    vigencia_inicio: date
    vigencia_fim: date | None = None
    fundamento_legal: str

    ncm: str | None = None
    cfop: str | None = None
    cst_csosn: str | None = None
    uf_origem: str | None = None
    uf_destino: str | None = None
    familia_material: str | None = None
    natureza_parceiro: str | None = None
    regime_parceiro: str | None = None
    parceiro_contribuinte: bool | None = None

    forma_calculo_base: str = "POR_FORA"
    aliquota: Decimal | None = None
    percentual_reducao_base: Decimal | None = None
    percentual_presuncao_base: Decimal | None = None
    valor_fixo: Decimal | None = None
    tratamento: str
    recuperabilidade: str = "NAO_APLICAVEL"
    percentual_recuperavel: Decimal | None = None
    prazo_realizacao_credito_dias: int | None = None

    compoe_deducao_venda: bool = False
    gera_credito_compra: bool = False
    compoe_custo_nao_recuperavel: bool = False
    incide_sobre_lucro: bool = False
    requer_confirmacao_condicao: bool = False
    condicao_descricao: str | None = None


class RegraTributariaOut(RegraTributariaIn):
    id: uuid.UUID
    status: str
    validado_por: str | None = None
    validado_em: date | None = None
    versao: int


class ValidacaoRegraIn(Base):
    """Promocao de PROVISORIA para VALIDADA -- ato do responsavel fiscal."""

    validado_por: str
    observacao: str | None = None


class ResultadoTributoOut(Base):
    """Saida obrigatoria do motor fiscal (secao 9.6)."""

    tributo: str
    tipo_operacao: str
    base_calculo: Decimal
    aliquota_nominal: Decimal
    aliquota_efetiva: Decimal
    valor_destacado: Decimal
    valor_devido: Decimal
    credito_entrada_relacionado: Decimal
    valor_recuperavel: Decimal
    efeito_liquido_resultado: Decimal
    efeito_caixa: Decimal
    data_provavel_caixa: date | None = None
    tratamento: str
    recuperabilidade: str
    fundamento_legal: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    codigo_regra: str | None = None
    status: str
    alerta: str | None = None
    efeito_percentual_sobre_preco: Decimal


class DeducoesIn(Base):
    contexto: ContextoFiscalIn
    comissao_percentual: Decimal = Decimal("0")
    desconto_contratual_percentual: Decimal = Decimal("0")


class DeducoesOut(Base):
    r_total: Decimal
    detalhamento: dict[str, Decimal]
    status_fiscal: str
    permite_cotacao_definitiva: bool
    tributos: list[ResultadoTributoOut]
    alertas: list[str] = Field(default_factory=list)
    memoria: MemoriaOut


class AliquotaSimplesIn(Base):
    rbt12: Decimal
    anexo: str = "ANEXO_II"
    icms_segregado: bool = False
    data_operacao: date | None = None


class AliquotaSimplesOut(Base):
    rbt12: Decimal
    ordem_faixa: int
    aliquota_nominal: Decimal
    aliquota_efetiva: Decimal
    aliquota_efetiva_sem_icms: Decimal
    percentual_icms: Decimal


class MudancaFaixaIn(Base):
    rbt12_atual: Decimal
    receita_mes_sem_a_venda: Decimal
    receita_da_venda: Decimal
    anexo: str = "ANEXO_II"


class MudancaFaixaOut(Base):
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
    alerta: str | None = None
