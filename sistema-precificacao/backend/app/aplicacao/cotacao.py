"""Caso de uso: gerar cotacao versionada com memoria de calculo.

Une o motor de custos e o motor fiscal, e materializa duas exigencias da
especificacao:

* a cotacao **congela** as premissas usadas (regra 9 da secao 11) -- alteracao
  posterior gera nova versao e a anterior continua reproduzivel;
* a cotacao nao pode ser definitiva com regra fiscal vencida, provisoria ou
  ausente (regra 2 da secao 11).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from app.dominio.camadas import ComponenteCusto, EstruturaCustos, montar_estrutura
from app.dominio.memoria import Memoria
from app.dominio.precos import EscadaPrecos, montar_escada
from app.dominio.unidades import ZERO, dec
from app.tributario.regimes import DeducoesVenda, calcular_deducoes_venda
from app.tributario.resolucao import ContextoFiscal

STATUS_DEFINITIVA = "DEFINITIVA"
STATUS_PROVISORIA = "PROVISORIA"
STATUS_BLOQUEADA = "BLOQUEADA"


@dataclass(frozen=True)
class PremissasCotacao:
    """Tudo que influencia o preco, congelado no momento do calculo.

    Sao estes valores -- e nao uma consulta nova ao banco -- que permitem
    reproduzir a cotacao meses depois, mesmo que taxas e regras tenham mudado.
    """

    data_referencia: date
    quantidade_kg: Decimal
    margem_alvo: Decimal
    margem_contribuicao_minima: Decimal
    componentes_custo: tuple[ComponenteCusto, ...]
    comissao_percentual: Decimal = ZERO
    desconto_contratual_percentual: Decimal = ZERO
    preco_mercado: Decimal | None = None
    observacao: str | None = None

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "data_referencia": self.data_referencia.isoformat(),
            "quantidade_kg": str(self.quantidade_kg),
            "margem_alvo": str(self.margem_alvo),
            "margem_contribuicao_minima": str(self.margem_contribuicao_minima),
            "comissao_percentual": str(self.comissao_percentual),
            "desconto_contratual_percentual": str(self.desconto_contratual_percentual),
            "preco_mercado": str(self.preco_mercado) if self.preco_mercado else None,
            "componentes_custo": [
                {
                    "nome": c.nome,
                    "valor": str(c.valor),
                    "camada_minima": c.camada_minima,
                    "visoes": list(c.visoes),
                    "e_desembolso": c.e_desembolso,
                }
                for c in self.componentes_custo
            ],
            "observacao": self.observacao,
        }


@dataclass(frozen=True)
class VersaoCotacao:
    """Uma versao imutavel da cotacao, com memoria de calculo propria."""

    numero: int
    premissas: PremissasCotacao
    estrutura: EstruturaCustos
    deducoes: DeducoesVenda
    escada: EscadaPrecos
    memoria: Memoria
    status: str
    alertas: tuple[str, ...] = field(default_factory=tuple)

    @property
    def permite_venda_definitiva(self) -> bool:
        return self.status == STATUS_DEFINITIVA

    def exportar(self) -> dict[str, Any]:
        """Pacote completo para auditoria e reproducao manual do preco."""

        return {
            "versao": self.numero,
            "status": self.status,
            "premissas": self.premissas.como_dicionario(),
            "deducoes_r": str(self.deducoes.r_total),
            "detalhamento_r": {
                k: str(v) for k, v in self.deducoes.detalhamento.items()
            },
            "precos": {
                camada: {
                    "custo_unitario": str(degrau.custo_unitario),
                    "preco_unitario": str(degrau.preco_unitario),
                    "margem_percentual": str(degrau.margem_percentual),
                    "finalidade": degrau.finalidade,
                }
                for camada, degrau in self.escada.degraus.items()
            },
            "memoria_calculo": self.memoria.exportar(),
            "alertas": list(self.alertas),
        }


def gerar_versao(
    premissas: PremissasCotacao,
    *,
    regras_fiscais: Iterable[Any],
    contexto_fiscal: ContextoFiscal,
    numero: int = 1,
    titulo: str = "Cotacao de venda",
) -> VersaoCotacao:
    """Calcula uma versao completa da cotacao."""

    memoria = Memoria(titulo=f"{titulo} - versao {numero}")

    estrutura = montar_estrutura(
        list(premissas.componentes_custo),
        quantidade_vendavel=premissas.quantidade_kg,
        memoria=memoria,
    )

    deducoes = calcular_deducoes_venda(
        regras_fiscais,
        contexto_fiscal,
        comissao_percentual=premissas.comissao_percentual,
        desconto_contratual_percentual=premissas.desconto_contratual_percentual,
        memoria=memoria,
    )

    escada = montar_escada(
        estrutura,
        deducoes_r=deducoes.r_total,
        margem_contribuicao_minima=premissas.margem_contribuicao_minima,
        margem_alvo=premissas.margem_alvo,
        preco_mercado=premissas.preco_mercado,
        quantidade=premissas.quantidade_kg,
        memoria=memoria,
    )

    alertas = list(deducoes.alertas) + list(escada.alertas) + list(memoria.alertas)

    if not deducoes.apuracao.resultados:
        status = STATUS_BLOQUEADA
        alertas.append(
            "Nenhuma regra tributaria aplicavel encontrada: cotacao bloqueada."
        )
    elif deducoes.permite_cotacao_definitiva:
        status = STATUS_DEFINITIVA
    else:
        status = STATUS_PROVISORIA
        alertas.append(
            f"Status fiscal {deducoes.apuracao.status_consolidado}: preco valido "
            f"apenas como estimativa, nao como cotacao definitiva."
        )

    return VersaoCotacao(
        numero=numero,
        premissas=premissas,
        estrutura=estrutura,
        deducoes=deducoes,
        escada=escada,
        memoria=memoria,
        status=status,
        alertas=tuple(dict.fromkeys(alertas)),
    )


def revisar(
    versao_anterior: VersaoCotacao,
    *,
    regras_fiscais: Iterable[Any],
    contexto_fiscal: ContextoFiscal,
    **alteracoes: Any,
) -> VersaoCotacao:
    """Gera nova versao a partir de outra, alterando apenas o que foi pedido.

    A versao anterior nao e tocada: ``replace`` produz novas premissas e o
    calculo roda do zero, preservando integralmente a memoria original
    (caso de teste 10).
    """

    novas_premissas = replace(versao_anterior.premissas, **alteracoes)
    return gerar_versao(
        novas_premissas,
        regras_fiscais=regras_fiscais,
        contexto_fiscal=contexto_fiscal,
        numero=versao_anterior.numero + 1,
    )


def reproduzir_preco(exportacao: dict[str, Any], camada: str) -> Decimal:
    """Recalcula o preco de uma camada a partir da exportacao da cotacao.

    Existe para provar o caso de teste 11: usando apenas o que foi exportado
    -- custo da camada, `r` e `m` --, qualquer pessoa chega ao mesmo preco
    pela formula P = C / [(1 - r) × (1 - m)].
    """

    from app.dominio.precos import calcular_preco

    dados_camada = exportacao["precos"][camada]
    custo = dec(dados_camada["custo_unitario"])
    r = dec(exportacao["deducoes_r"])

    premissas = exportacao["premissas"]
    if camada == "ALVO":
        m = dec(premissas["margem_alvo"])
    elif camada == "CONTRIBUICAO":
        m = dec(premissas["margem_contribuicao_minima"])
    else:
        m = ZERO

    return calcular_preco(custo, r, m, rotulo=f"reproducao de {camada}")
