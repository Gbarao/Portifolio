"""Base declarativa, tipos monetarios e mixins compartilhados.

Decisoes registradas aqui valem para todo o schema:

* Dinheiro e quantidade usam ``Numeric`` (nunca ``Float``): o modelo exige
  reprodutibilidade da memoria de calculo, e ponto flutuante binario nao
  reproduz o mesmo centavo duas vezes.
* Toda medida e persistida ja normalizada em unidade-padrao (kg, km, hora,
  BRL), preservando a unidade original do documento em campo proprio.
* Registros financeiros e fiscais carregam data de competencia e data de
  caixa separadas, conforme secao 10 da especificacao.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from sqlalchemy import JSON, Date, DateTime, MetaData, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomes deterministicos de constraints: migracoes do Alembic precisam
# conseguir referenciar indices e chaves pelo nome em qualquer banco.
CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Escalas: 6 casas cobrem R$/kg com folga (R$ 0,000001) e evitam erro
# acumulado ao converter tonelada <-> quilograma.
TIPO_DINHEIRO = Numeric(18, 6)
TIPO_QUANTIDADE = Numeric(18, 6)
TIPO_PERCENTUAL = Numeric(12, 8)

Dinheiro = Annotated[Decimal, mapped_column(TIPO_DINHEIRO)]
DinheiroOpc = Annotated[Decimal | None, mapped_column(TIPO_DINHEIRO)]
Quantidade = Annotated[Decimal, mapped_column(TIPO_QUANTIDADE)]
QuantidadeOpc = Annotated[Decimal | None, mapped_column(TIPO_QUANTIDADE)]
Percentual = Annotated[Decimal, mapped_column(TIPO_PERCENTUAL)]
PercentualOpc = Annotated[Decimal | None, mapped_column(TIPO_PERCENTUAL)]
Texto = Annotated[str, mapped_column(Text)]
TextoOpc = Annotated[str | None, mapped_column(Text)]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_NOMES)

    type_annotation_map = {
        Decimal: TIPO_DINHEIRO,
        datetime: DateTime(timezone=True),
        date: Date,
        uuid.UUID: Uuid,
        str: String(255),
        dict[str, Any]: JSON,
    }

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        identificador = getattr(self, "id", None)
        return f"<{type(self).__name__} {identificador}>"


class IdMixin:
    """Chave primaria UUID: identificadores nao sequenciais evitam vazar
    volume de operacao para parceiros e sobrevivem a consolidacao de bases."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class VigenciaMixin:
    """Parametros e regras nunca sao sobrescritos: ganham nova vigencia.

    ``vigencia_fim`` nulo significa vigencia aberta. A selecao correta e sempre
    pela data da operacao, nunca pela data de hoje.
    """

    vigencia_inicio: Mapped[date]
    vigencia_fim: Mapped[date | None]
    versao: Mapped[int] = mapped_column(default=1)
    fonte: Mapped[str | None]
    aprovado_por: Mapped[str | None]
    aprovado_em: Mapped[date | None]


class CompetenciaCaixaMixin:
    """Competencia move resultado; caixa move capital de giro. Sao datas
    diferentes e o modelo depende das duas."""

    data_competencia: Mapped[date]
    data_caixa: Mapped[date | None]
