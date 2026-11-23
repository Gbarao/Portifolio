"""Regras legais versionadas (param_regras_legais): percentuais, prazos e vigencias.

Nenhum percentual da LC 214/2025 fica fixo no codigo: tudo e lido desta tabela. Uma regra so e
aplicada se o status for 'vigente' ou 'futura' e o ano/data estiver entre o inicio e o fim da
vigencia. Regra 'pendente_regulamentacao' ou 'revogada' nao e aplicada e o resultado e sinalizado.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

import pandas as pd

from . import params

APLICAVEIS = ("vigente", "futura")


@dataclass(frozen=True)
class Regra:
    codigo: str
    percentual: float | None
    inicio: _dt.date | None
    fim: _dt.date | None
    status: str
    dispositivo: str
    descricao: str
    observacao: str

    def vigente_em(self, data: _dt.date) -> bool:
        if self.status not in APLICAVEIS:
            return False
        if self.inicio and data < self.inicio:
            return False
        return not (self.fim and data > self.fim)

    def vigente_no_ano(self, ano: int) -> bool:
        """Vale para o ano se estiver vigente em algum dia do ano."""
        if self.status not in APLICAVEIS:
            return False
        if self.inicio and self.inicio > _dt.date(ano, 12, 31):
            return False
        return not (self.fim and self.fim < _dt.date(ano, 1, 1))


def _data(v) -> _dt.date | None:
    t = str(v or "").strip()
    if not t:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return _dt.datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def carregar() -> dict[str, Regra]:
    df = params.carregar("param_regras_legais")
    out = {}
    for r in df.itertuples():
        pct = float(r.percentual) if r.percentual is not None and pd.notna(r.percentual) else None
        out[r.codigo] = Regra(r.codigo, pct, _data(r.inicio_vigencia), _data(r.fim_vigencia),
                              str(r.status).strip().lower(), r.dispositivo, r.descricao, r.observacao)
    return out


def regra(codigo: str, tabela: dict[str, Regra] | None = None) -> Regra | None:
    return (tabela or carregar()).get(codigo)


def pct(codigo: str, tabela: dict[str, Regra] | None = None, padrao: float | None = None) -> float | None:
    """Percentual cadastrado (sem olhar vigencia). None = nao parametrizado."""
    r = regra(codigo, tabela)
    return r.percentual if r and r.percentual is not None else padrao


def fator(codigo: str, ano: int, tabela: dict[str, Regra] | None = None) -> float:
    """1.0 se a regra vale no ano, 0.0 se nao (inclusive pendente de regulamentacao ou revogada)."""
    r = regra(codigo, tabela)
    return 1.0 if r and r.vigente_no_ano(ano) else 0.0


def pendencias(tabela: dict[str, Regra] | None = None) -> list[Regra]:
    t = tabela or carregar()
    return [r for r in t.values() if r.status == "pendente_regulamentacao"]
