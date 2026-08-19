"""Saidas do motor fiscal (secao 9.6).

Para cada simulacao ou venda o sistema precisa exibir: tributo, base, aliquota
nominal e efetiva, valor destacado, devido, credito relacionado, valor
recuperavel, efeito no resultado, efeito e data no caixa, fundamento, vigencia
e status. A dataclass abaixo e exatamente essa lista.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.dominio.unidades import ZERO

STATUS_VALIDADA = "VALIDADA"
STATUS_PROVISORIA = "PROVISORIA"
STATUS_VENCIDA = "VENCIDA"
STATUS_BLOQUEADA = "BLOQUEADA"

# Status que impedem classificar a cotacao como definitiva (regra 2, secao 11).
STATUS_QUE_BLOQUEIAM_COTACAO = {STATUS_PROVISORIA, STATUS_VENCIDA, STATUS_BLOQUEADA}


@dataclass(frozen=True)
class ResultadoTributo:
    """Efeito de uma regra tributaria sobre uma operacao."""

    tributo: str
    tipo_operacao: str
    base_calculo: Decimal
    aliquota_nominal: Decimal
    aliquota_efetiva: Decimal
    valor_destacado: Decimal
    valor_devido: Decimal
    credito_entrada_relacionado: Decimal = ZERO
    valor_recuperavel: Decimal = ZERO
    efeito_liquido_resultado: Decimal = ZERO
    efeito_caixa: Decimal = ZERO
    data_provavel_caixa: date | None = None
    tratamento: str = ""
    recuperabilidade: str = ""
    fundamento_legal: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    versao_regra: int | None = None
    codigo_regra: str | None = None
    status: str = STATUS_PROVISORIA
    alerta: str | None = None
    # Fracao do preco bruto que esta regra consome. Alimenta a variavel `r`.
    efeito_percentual_sobre_preco: Decimal = ZERO


@dataclass
class ApuracaoOperacao:
    """Conjunto de resultados de uma operacao, com status consolidado."""

    resultados: list[ResultadoTributo] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)

    @property
    def status_consolidado(self) -> str:
        """O status mais restritivo entre as regras aplicadas.

        Uma unica regra vencida contamina a operacao inteira: nao existe
        cotacao "parcialmente definitiva".
        """

        if not self.resultados:
            return STATUS_BLOQUEADA
        for status in (STATUS_BLOQUEADA, STATUS_VENCIDA, STATUS_PROVISORIA):
            if any(r.status == status for r in self.resultados):
                return status
        return STATUS_VALIDADA

    @property
    def permite_cotacao_definitiva(self) -> bool:
        return self.status_consolidado not in STATUS_QUE_BLOQUEIAM_COTACAO

    def por_tributo(self, tributo: str) -> ResultadoTributo | None:
        for resultado in self.resultados:
            if resultado.tributo == tributo:
                return resultado
        return None
