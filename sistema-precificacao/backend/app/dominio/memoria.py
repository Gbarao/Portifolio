"""Memoria de calculo: o registro reproduzivel de cada passo.

A secao 15 e a regra 15 da secao 11 exigem que qualquer numero produzido pelo
sistema possa ser refeito a mao a partir do que ficou armazenado. Por isso
todo calculo relevante registra aqui um passo com rotulo, formula legivel,
entradas nomeadas, resultado, unidade, fonte, vigencia e status do dado.

O objeto e puro: nao conhece banco. A camada de aplicacao converte estes
passos nas tabelas ``memoria_calculo`` e ``memoria_passo``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.dominio.unidades import dec

STATUS_CONFIRMADO = "CONFIRMADO"
STATUS_ESTIMADO = "ESTIMADO"
STATUS_PROVISORIO = "PROVISORIO"


@dataclass(frozen=True)
class Passo:
    """Um passo reproduzivel do calculo."""

    ordem: int
    rotulo: str
    formula: str
    entradas: dict[str, Any]
    resultado: Decimal
    unidade: str
    fonte: str | None = None
    vigencia_regra: str | None = None
    status_dado: str = STATUS_CONFIRMADO
    alerta: str | None = None

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "ordem": self.ordem,
            "rotulo": self.rotulo,
            "formula": self.formula,
            "entradas": {k: str(v) for k, v in self.entradas.items()},
            "resultado": str(self.resultado),
            "unidade": self.unidade,
            "fonte": self.fonte,
            "vigencia_regra": self.vigencia_regra,
            "status_dado": self.status_dado,
            "alerta": self.alerta,
        }


@dataclass
class Memoria:
    """Coletor de passos de um calculo.

    Uso tipico: a funcao de dominio recebe ``memoria`` opcional e registra
    seus passos. Quando ``None``, o calculo roda sem custo de rastreamento --
    util em simulacoes de milhares de cenarios.
    """

    titulo: str = "Calculo"
    passos: list[Passo] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)

    def registrar(
        self,
        rotulo: str,
        formula: str,
        entradas: dict[str, Any],
        resultado: Any,
        unidade: str,
        *,
        fonte: str | None = None,
        vigencia_regra: str | None = None,
        status_dado: str = STATUS_CONFIRMADO,
        alerta: str | None = None,
    ) -> Decimal:
        """Registra um passo e devolve o proprio resultado.

        Devolver o resultado permite escrever
        ``total = memoria.registrar(..., resultado=a + b, ...)``
        sem duplicar a expressao.
        """

        valor = dec(resultado)
        self.passos.append(
            Passo(
                ordem=len(self.passos) + 1,
                rotulo=rotulo,
                formula=formula,
                entradas=entradas,
                resultado=valor,
                unidade=unidade,
                fonte=fonte,
                vigencia_regra=vigencia_regra,
                status_dado=status_dado,
                alerta=alerta,
            )
        )
        if alerta:
            self.alertas.append(alerta)
        return valor

    def alertar(self, mensagem: str) -> None:
        """Alerta que nao corresponde a um passo de calculo."""

        self.alertas.append(mensagem)

    def resultado_de(self, rotulo: str) -> Decimal | None:
        """Recupera o resultado do ultimo passo com determinado rotulo."""

        for passo in reversed(self.passos):
            if passo.rotulo == rotulo:
                return passo.resultado
        return None

    def exportar(self) -> dict[str, Any]:
        """Serializa a memoria completa.

        E esta estrutura que sustenta o caso de teste 11: o usuario deve
        conseguir reproduzir o preco a partir dos dados e formulas exportados.
        """

        return {
            "titulo": self.titulo,
            "passos": [p.como_dicionario() for p in self.passos],
            "alertas": list(self.alertas),
        }

    def texto(self) -> str:
        """Versao legivel para conferencia humana e exportacao em relatorio."""

        linhas = [self.titulo, "=" * len(self.titulo)]
        for passo in self.passos:
            linhas.append(f"{passo.ordem:>2}. {passo.rotulo}")
            linhas.append(f"    formula: {passo.formula}")
            for nome, valor in passo.entradas.items():
                linhas.append(f"    {nome} = {valor}")
            linhas.append(f"    -> {passo.resultado} {passo.unidade}")
            if passo.alerta:
                linhas.append(f"    ! {passo.alerta}")
        if self.alertas:
            linhas.append("")
            linhas.append("Alertas:")
            linhas.extend(f"  - {a}" for a in self.alertas)
        return "\n".join(linhas)
