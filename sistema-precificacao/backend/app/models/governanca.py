"""Memoria de calculo, alertas, fechamento mensal e trilha de auditoria
(secoes 11, 13.3 e 15)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    Dinheiro,
    DinheiroOpc,
    IdMixin,
    PercentualOpc,
    Texto,
    TextoOpc,
    TimestampMixin,
)
from app.models._tipos import coluna_enum
from app.models.enums import AcaoAuditoria, StatusDado, StatusRegraFiscal


class MemoriaCalculo(IdMixin, TimestampMixin, Base):
    """Cabecalho da memoria de calculo de um lote, cotacao ou simulacao.

    Sem ela nao ha cotacao definitiva: a regra 15 da secao 11 exige que toda
    formula seja reproduzivel a partir do que foi armazenado.
    """

    __tablename__ = "memoria_calculo"

    escopo: Mapped[str]  # LOTE_COMPRA | COTACAO_VERSAO | SIMULACAO | FRETE
    referencia_id: Mapped[uuid.UUID]
    titulo: Mapped[str]
    versao_regras: Mapped[dict[str, Any] | None]
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    status_fiscal: Mapped[StatusRegraFiscal | None] = coluna_enum(
        StatusRegraFiscal, nullable=True
    )
    criado_por: Mapped[str | None]

    passos: Mapped[list["MemoriaPasso"]] = relationship(
        back_populates="memoria", order_by="MemoriaPasso.ordem"
    )


class MemoriaPasso(IdMixin, Base):
    """Um passo reproduzivel: formula, entradas, fonte, vigencia e resultado."""

    __tablename__ = "memoria_passo"
    __table_args__ = (UniqueConstraint("memoria_id", "ordem"),)

    memoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memoria_calculo.id"))
    ordem: Mapped[int]
    rotulo: Mapped[str]
    formula: Mapped[Texto]
    entradas: Mapped[dict[str, Any]]
    resultado: Mapped[Dinheiro]
    unidade: Mapped[str]
    fonte: Mapped[str | None]
    vigencia_regra: Mapped[str | None]
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    alerta: Mapped[TextoOpc]

    memoria: Mapped[MemoriaCalculo] = relationship(back_populates="passos")


class Alerta(IdMixin, TimestampMixin, Base):
    """Alertas que a interface exibe e que podem bloquear operacoes.

    ``bloqueante`` distingue aviso de trava: regra fiscal vencida bloqueia a
    cotacao definitiva mesmo com todos os demais campos preenchidos
    (secao 16).
    """

    __tablename__ = "alerta"

    escopo: Mapped[str]
    referencia_id: Mapped[uuid.UUID]
    codigo: Mapped[str]
    severidade: Mapped[str]  # INFO | ATENCAO | CRITICO
    bloqueante: Mapped[bool] = mapped_column(default=False)
    mensagem: Mapped[Texto]
    contexto: Mapped[dict[str, Any] | None]
    resolvido: Mapped[bool] = mapped_column(default=False)
    resolvido_por: Mapped[str | None]
    resolvido_em: Mapped[datetime | None]
    justificativa_resolucao: Mapped[TextoOpc]


class FechamentoMensal(IdMixin, TimestampMixin, Base):
    """Reconciliacao do periodo (secao 13.3).

    Guarda explicitamente o custo de ociosidade, que nunca e transferido
    automaticamente para os produtos (secao 7.3).
    """

    __tablename__ = "fechamento_mensal"
    __table_args__ = (UniqueConstraint("unidade_id", "competencia"),)

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    competencia: Mapped[date]
    status: Mapped[str] = mapped_column(default="ABERTO")

    custo_ociosidade: Mapped[Dinheiro] = mapped_column(default=0)
    perda_anormal_valor: Mapped[Dinheiro] = mapped_column(default=0)
    resultado_operacional: Mapped[DinheiroOpc]
    resultado_completo: Mapped[DinheiroOpc]
    divergencia_reconciliacao: Mapped[DinheiroOpc]
    divergencia_percentual: Mapped[PercentualOpc]

    reconciliacoes: Mapped[dict[str, Any] | None]
    desvios: Mapped[dict[str, Any] | None]
    aprovado_por: Mapped[str | None]
    aprovado_em: Mapped[datetime | None]
    observacao: Mapped[TextoOpc]


class Auditoria(IdMixin, Base):
    """Trilha append-only: quem mudou o que, quando e por que (secao 10)."""

    __tablename__ = "auditoria"

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    usuario_nome: Mapped[str | None]
    entidade: Mapped[str]
    registro_id: Mapped[uuid.UUID | None]
    acao: Mapped[AcaoAuditoria] = coluna_enum(AcaoAuditoria)
    valor_anterior: Mapped[dict[str, Any] | None]
    valor_novo: Mapped[dict[str, Any] | None]
    justificativa: Mapped[TextoOpc]
    endereco_origem: Mapped[str | None]
    criado_em: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now().astimezone()
    )
