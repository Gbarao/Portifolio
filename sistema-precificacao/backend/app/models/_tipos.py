"""Auxiliares de mapeamento reutilizados pelos modelos."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import mapped_column


def coluna_enum(enum_cls: type[StrEnum], **kwargs: Any):
    """Persiste enums como texto com CHECK constraint.

    Evita ``ALTER TYPE`` a cada novo tributo, tratamento ou direcionador --
    o vocabulario do dominio ainda vai crescer conforme a matriz tributaria
    for validada pelo contador.
    """

    return mapped_column(
        SAEnum(
            enum_cls,
            native_enum=False,
            length=48,
            values_callable=lambda e: [membro.value for membro in e],
        ),
        **kwargs,
    )
