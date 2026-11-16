"""Filtro global (empresas, estabelecimentos e periodo) aplicado no SQL."""
from __future__ import annotations

import re
from dataclasses import dataclass


def _seguro(v: str) -> str:
    # CNPJ (inclusive alfanumerico, a partir de 2026) e raiz: so letras e digitos
    return re.sub(r"[^0-9A-Za-z]", "", str(v))


@dataclass(frozen=True)
class Filtro:
    raizes: tuple[str, ...] | None = None      # None = todas
    estabs: tuple[str, ...] | None = None      # None = todos os estabelecimentos
    mes_ini: int = 1
    mes_fim: int = 12

    def sql(self, raiz: str | None = "raiz", estab: str | None = "cnpj_estab",
            mes: str | None = "mes") -> str:
        cond = ["TRUE"]
        if raiz and self.raizes is not None:
            lista = ", ".join(f"'{_seguro(r)}'" for r in self.raizes) or "''"
            cond.append(f"{raiz} IN ({lista})")
        if estab and self.estabs is not None:
            lista = ", ".join(f"'{_seguro(e)}'" for e in self.estabs) or "''"
            cond.append(f"{estab} IN ({lista})")
        if mes:
            cond.append(f"{mes} BETWEEN {int(self.mes_ini)} AND {int(self.mes_fim)}")
        return " AND ".join(cond)

    @property
    def meses(self) -> list[int]:
        return list(range(int(self.mes_ini), int(self.mes_fim) + 1))


TODOS = Filtro()
