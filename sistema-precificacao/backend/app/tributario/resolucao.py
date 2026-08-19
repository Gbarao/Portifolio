"""Resolucao da regra tributaria aplicavel (secao 9.2).

A regra e escolhida por duas dimensoes:

1. **Compatibilidade** -- toda chave preenchida na regra precisa bater com o
   contexto da operacao. Chave nula e coringa.
2. **Especificidade** -- entre as compativeis, vence a que tem mais chaves
   preenchidas. Uma regra de ICMS para "SP -> SP, sucata, cliente
   contribuinte" prevalece sobre a regra geral de ICMS.

A vigencia e sempre avaliada pela **data da operacao**, nunca pela data de
hoje: refazer uma cotacao de marco tem que produzir o preco de marco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Protocol

from app.tributario.resultado import STATUS_VENCIDA


@dataclass
class ContextoFiscal:
    """Chaves da operacao que serao confrontadas com as regras."""

    data_operacao: date
    tipo_operacao: str
    regime_tributario: str
    uf_origem: str | None = None
    uf_destino: str | None = None
    municipio: str | None = None
    ncm: str | None = None
    cfop: str | None = None
    cst_csosn: str | None = None
    familia_material: str | None = None
    material_id: Any = None
    natureza_parceiro: str | None = None
    regime_parceiro: str | None = None
    parceiro_contribuinte: bool | None = None
    empresa_id: Any = None
    unidade_id: Any = None


class RegraProtocolo(Protocol):
    """Interface minima esperada de uma regra.

    Aceita tanto o modelo ORM ``RegraTributaria`` quanto qualquer objeto
    equivalente construido em teste -- o motor nao depende do banco.
    """

    codigo: str
    tipo_operacao: Any
    tributo: Any
    vigencia_inicio: date
    vigencia_fim: date | None


# Chaves comparadas entre regra e contexto. A ordem nao importa; a contagem
# de acertos define a especificidade.
CHAVES_COMPARADAS = (
    "regime_tributario",
    "uf_origem",
    "uf_destino",
    "municipio",
    "ncm",
    "cfop",
    "cst_csosn",
    "familia_material",
    "material_id",
    "natureza_parceiro",
    "regime_parceiro",
    "parceiro_contribuinte",
    "empresa_id",
    "unidade_id",
)


def _valor(objeto: Any, campo: str) -> Any:
    """Le o campo normalizando enums para o proprio valor textual."""

    valor = getattr(objeto, campo, None)
    return getattr(valor, "value", valor)


def esta_vigente(regra: RegraProtocolo, data_operacao: date) -> bool:
    inicio = regra.vigencia_inicio
    fim = regra.vigencia_fim
    if inicio is not None and data_operacao < inicio:
        return False
    if fim is not None and data_operacao > fim:
        return False
    return True


def _compativel(regra: Any, contexto: ContextoFiscal) -> tuple[bool, int]:
    """Devolve (compativel, especificidade)."""

    if _valor(regra, "tipo_operacao") != contexto.tipo_operacao:
        return False, 0

    especificidade = 0
    for chave in CHAVES_COMPARADAS:
        valor_regra = _valor(regra, chave)
        if valor_regra is None:
            continue  # coringa
        valor_contexto = getattr(contexto, chave, None)
        valor_contexto = getattr(valor_contexto, "value", valor_contexto)
        if valor_regra != valor_contexto:
            return False, 0
        especificidade += 1

    return True, especificidade


@dataclass
class ResolucaoRegras:
    """Regras escolhidas e as que ficaram de fora por vigencia."""

    aplicaveis: list[Any] = field(default_factory=list)
    vencidas: list[Any] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)

    @property
    def ha_regra_vencida(self) -> bool:
        return bool(self.vencidas)


def resolver(
    regras: Iterable[Any],
    contexto: ContextoFiscal,
    *,
    tributos_exigidos: Iterable[str] | None = None,
) -> ResolucaoRegras:
    """Seleciona uma regra por tributo: a mais especifica e vigente.

    Regras compativeis mas fora de vigencia nao sao ignoradas em silencio --
    vao para ``vencidas`` e geram alerta, porque a ausencia de regra vigente e
    justamente o que bloqueia a cotacao definitiva (regra 2 da secao 11).
    """

    resolucao = ResolucaoRegras()
    candidatas: dict[str, tuple[int, Any]] = {}

    for regra in regras:
        compativel, especificidade = _compativel(regra, contexto)
        if not compativel:
            continue

        tributo = _valor(regra, "tributo")

        if not esta_vigente(regra, contexto.data_operacao):
            resolucao.vencidas.append(regra)
            resolucao.alertas.append(
                f"Regra {getattr(regra, 'codigo', tributo)} ({tributo}) esta fora de "
                f"vigencia em {contexto.data_operacao.isoformat()}: "
                f"cotacao definitiva bloqueada ate revalidacao."
            )
            continue

        melhor = candidatas.get(tributo)
        if melhor is None or especificidade > melhor[0]:
            candidatas[tributo] = (especificidade, regra)

    resolucao.aplicaveis = [regra for _, regra in candidatas.values()]

    for tributo in tributos_exigidos or ():
        if tributo not in candidatas:
            resolucao.alertas.append(
                f"Nenhuma regra vigente para {tributo} em "
                f"{contexto.data_operacao.isoformat()}: calculo marcado como "
                f"provisorio."
            )

    return resolucao


def status_da_regra(regra: Any, data_operacao: date) -> str:
    """Status efetivo da regra na data da operacao.

    Uma regra cadastrada como VALIDADA mas fora de vigencia vale VENCIDA:
    o que decide e a data da operacao, nao o carimbo do cadastro.
    """

    if not esta_vigente(regra, data_operacao):
        return STATUS_VENCIDA
    return _valor(regra, "status") or "PROVISORIA"
