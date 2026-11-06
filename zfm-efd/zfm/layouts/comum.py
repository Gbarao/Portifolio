"""Estruturas comuns aos dicionarios de layout SPED.

Cada registro tem uma lista de VERSOES de layout (da mais nova para a mais
antiga). Cada versao lista os campos na ordem do Guia Pratico. A escolha da
versao usada em cada linha e feita assim (ver DECISOES.md, D-003):

1. versoes cujo ``cod_ver`` inclui o COD_VER do arquivo e cujo numero de
   campos coincide com o da linha;
2. qualquer versao cujo numero de campos coincide com o da linha;
3. a versao mais nova, com aviso de divergencia de numero de campos.

Os campos sao sempre acessados pelo NOME, nunca por indice solto no codigo.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VersaoLayout:
    rotulo: str
    campos: tuple[str, ...]
    # COD_VER em que esta versao vale. Vazio = nao confirmado (escolha por
    # numero de campos). Conferir no Guia Pratico antes de preencher.
    cod_ver: tuple[str, ...] = ()
    observacao: str = ""

    @property
    def n(self) -> int:
        return len(self.campos)


@dataclass(frozen=True)
class Registro:
    reg: str
    descricao: str
    versoes: tuple[VersaoLayout, ...]
    pai: str | None = None  # registro pai (hierarquia por ordem)
    # Quando o registro define o estabelecimento dos filhos (C010, 0140...)
    campo_cnpj_estab: str | None = None
    carregar: bool = True

    @property
    def campos_uniao(self) -> tuple[str, ...]:
        """Uniao ordenada dos campos de todas as versoes (colunas da tabela)."""
        vistos: list[str] = []
        for v in self.versoes:
            for c in v.campos:
                if c not in vistos:
                    vistos.append(c)
        return tuple(vistos)

    def escolher_versao(self, n_campos: int, cod_ver: str | None) -> tuple[VersaoLayout, bool]:
        """Retorna (versao, exato). ``exato`` = numero de campos confere."""
        if cod_ver:
            for v in self.versoes:
                if cod_ver in v.cod_ver and v.n == n_campos:
                    return v, True
        for v in self.versoes:
            if v.n == n_campos:
                return v, True
        return self.versoes[0], False


def campos(texto: str) -> tuple[str, ...]:
    return tuple(texto.split())


def reg(codigo: str, descricao: str, *versoes: VersaoLayout | str, pai: str | None = None,
        campo_cnpj_estab: str | None = None, carregar: bool = True) -> Registro:
    vs: list[VersaoLayout] = []
    for i, v in enumerate(versoes):
        if isinstance(v, str):
            v = VersaoLayout(rotulo=f"v{len(versoes) - i}", campos=campos(v))
        vs.append(v)
    for v in vs:
        if v.campos[0] != "REG":
            raise ValueError(f"Layout {codigo}: primeiro campo deve ser REG")
    return Registro(codigo, descricao, tuple(vs), pai, campo_cnpj_estab, carregar)


# ---------------------------------------------------------------------------
# Tipos de coluna no DuckDB (derivados do nome do campo; excecoes explicitas)
# ---------------------------------------------------------------------------
_INTEIROS = {"QTD_REG_BLC", "QTD_LIN", "QTD_LIN_0", "QTD_LIN_C", "QTD_LIN_E", "QTD_LIN_9"}
_TEXTO = {"PER_APU_CRED", "MES_REF", "DT_REF"}
_DECIMAL_6 = {"VL_UNIT", "ALIQ_PIS_QUANT", "ALIQ_COFINS_QUANT"}


def tipo_coluna(nome: str) -> str:
    if nome in _TEXTO:
        return "VARCHAR"
    if nome in _INTEIROS:
        return "BIGINT"
    if nome.startswith("DT_"):
        return "DATE"
    if nome in _DECIMAL_6:
        return "DECIMAL(24,6)"
    if nome.startswith("ALIQ"):
        return "DECIMAL(18,4)"
    if nome == "QTD" or nome.startswith("QUANT_") or nome.startswith("QTD_"):
        return "DECIMAL(24,6)"
    if nome.startswith(("VL_", "SLD_", "SD_")) or nome == "DEB_ESP":
        return "DECIMAL(18,2)"
    return "VARCHAR"
