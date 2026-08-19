"""Aplicacao de uma regra tributaria sobre uma base (secoes 7.6 e 9.6).

A secao 7.6 adverte: aliquotas nao podem ser somadas sem analisar a base.
Tributo por dentro, base reduzida, presuncao, pauta e valor fixo produzem
efeitos diferentes sobre o preco, e e aqui que essa diferenca e resolvida.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.dominio.memoria import Memoria
from app.dominio.unidades import UM, ZERO, dec
from app.tributario.resolucao import status_da_regra
from app.tributario.resultado import ResultadoTributo

FORMA_POR_FORA = "POR_FORA"
FORMA_POR_DENTRO = "POR_DENTRO"
FORMA_BASE_REDUZIDA = "BASE_REDUZIDA"
FORMA_VALOR_FIXO = "VALOR_FIXO"
FORMA_PAUTA = "PAUTA"

TRATAMENTOS_SEM_ONUS = {"ISENCAO", "SUSPENSAO", "DIFERIMENTO", "NAO_TRIBUTADO"}
RECUPERABILIDADE_ELEGIVEL = "ELEGIVEL"
RECUPERABILIDADE_CONDICIONADA = "CONDICIONADA"
RECUPERABILIDADE_PROPORCIONAL = "PROPORCIONAL"


def _v(regra: Any, campo: str, padrao: Any = None) -> Any:
    valor = getattr(regra, campo, None)
    valor = getattr(valor, "value", valor)
    return padrao if valor is None else valor


def aplicar_regra(
    regra: Any,
    *,
    base_bruta: Decimal,
    data_operacao: date,
    quantidade: Decimal | None = None,
    condicao_confirmada: bool = False,
    memoria: Memoria | None = None,
) -> ResultadoTributo:
    """Calcula base, aliquota efetiva e valores de uma regra.

    ``condicao_confirmada`` responde a pergunta que a Lei 15.394/2026 impoe:
    o adquirente esta no lucro real e usa o residuo como materia-prima? Sem
    essa confirmacao o credito e apurado mas nao reduz custo algum.
    """

    base_bruta = dec(base_bruta)
    forma = _v(regra, "forma_calculo_base", FORMA_POR_FORA)
    aliquota = dec(_v(regra, "aliquota", ZERO))
    reducao = dec(_v(regra, "percentual_reducao_base", ZERO))
    presuncao = _v(regra, "percentual_presuncao_base")
    tratamento = _v(regra, "tratamento", "DEBITO")
    recuperabilidade = _v(regra, "recuperabilidade", "NAO_APLICAVEL")
    status = status_da_regra(regra, data_operacao)
    alertas: list[str] = []

    # --- base de calculo ---
    if forma == FORMA_VALOR_FIXO:
        base = base_bruta
        valor = dec(_v(regra, "valor_fixo", ZERO))
        efetiva = dec(0) if base == ZERO else valor / base
    elif forma == FORMA_PAUTA:
        pauta = dec(_v(regra, "valor_pauta_unitario", ZERO))
        base = pauta * dec(quantidade or ZERO)
        valor = base * aliquota
        efetiva = dec(0) if base_bruta == ZERO else valor / base_bruta
    elif forma == FORMA_BASE_REDUZIDA and presuncao is not None:
        # Presuncao do lucro presumido: base = receita × presuncao.
        base = base_bruta * dec(presuncao)
        valor = base * aliquota
        # Sobre o preco bruto, o efeito e presuncao × aliquota.
        efetiva = dec(presuncao) * aliquota
    else:
        base = base_bruta * (UM - reducao)
        valor = base * aliquota
        efetiva = aliquota * (UM - reducao)

    # --- tratamento ---
    if tratamento in TRATAMENTOS_SEM_ONUS:
        valor_devido = ZERO
        efetiva_final = ZERO
        if tratamento == "DIFERIMENTO":
            alertas.append(
                f"{_v(regra, 'tributo')} diferido: não onera esta operação, mas o "
                f"tributo permanece na cadeia e deve ser acompanhado."
            )
    else:
        valor_devido = valor
        efetiva_final = efetiva

    # --- credito e recuperabilidade ---
    credito = ZERO
    recuperavel = ZERO
    gera_credito = bool(_v(regra, "gera_credito_compra", False))
    requer_confirmacao = bool(_v(regra, "requer_confirmacao_condicao", False))

    if gera_credito:
        credito = valor
        if recuperabilidade == RECUPERABILIDADE_ELEGIVEL:
            recuperavel = credito
        elif recuperabilidade == RECUPERABILIDADE_PROPORCIONAL:
            recuperavel = credito * dec(_v(regra, "percentual_recuperavel", ZERO))
        elif recuperabilidade == RECUPERABILIDADE_CONDICIONADA:
            if requer_confirmacao and not condicao_confirmada:
                recuperavel = ZERO
                alertas.append(
                    f"Crédito de {_v(regra, 'tributo')} condicionado e não "
                    f"confirmado: não reduziu o custo. Condição: "
                    f"{_v(regra, 'condicao_descricao', 'não descrita')}"
                )
            else:
                recuperavel = credito * dec(_v(regra, "percentual_recuperavel", UM))
        else:
            # VEDADA ou NAO_APLICAVEL: nao ha credito aproveitavel.
            recuperavel = ZERO
            if recuperabilidade == "VEDADA":
                alertas.append(
                    f"Crédito de {_v(regra, 'tributo')} vedado neste regime: "
                    f"o valor permanece como custo."
                )

    prazo = _v(regra, "prazo_realizacao_credito_dias")
    data_caixa = data_operacao + timedelta(days=int(prazo)) if prazo else None

    resultado = ResultadoTributo(
        tributo=str(_v(regra, "tributo")),
        tipo_operacao=str(_v(regra, "tipo_operacao")),
        base_calculo=base,
        aliquota_nominal=aliquota,
        aliquota_efetiva=efetiva_final,
        valor_destacado=valor,
        valor_devido=valor_devido,
        credito_entrada_relacionado=credito,
        valor_recuperavel=recuperavel,
        efeito_liquido_resultado=valor_devido - recuperavel,
        efeito_caixa=valor_devido - recuperavel,
        data_provavel_caixa=data_caixa,
        tratamento=str(tratamento),
        recuperabilidade=str(recuperabilidade),
        fundamento_legal=_v(regra, "fundamento_legal"),
        vigencia_inicio=getattr(regra, "vigencia_inicio", None),
        vigencia_fim=getattr(regra, "vigencia_fim", None),
        versao_regra=_v(regra, "versao"),
        codigo_regra=_v(regra, "codigo"),
        status=status,
        alerta="; ".join(alertas) if alertas else None,
        efeito_percentual_sobre_preco=(
            efetiva_final if bool(_v(regra, "compoe_deducao_venda", False)) else ZERO
        ),
    )

    if memoria is not None:
        memoria.registrar(
            f"{resultado.tributo} ({resultado.tipo_operacao})",
            {
                FORMA_POR_DENTRO: "valor = base × alíquota (tributo por dentro)",
                FORMA_BASE_REDUZIDA: "base = receita × presunção; valor = base × alíquota",
                FORMA_VALOR_FIXO: "valor fixo definido em regra",
                FORMA_PAUTA: "base = pauta unitária × quantidade; valor = base × alíquota",
            }.get(forma, "base = base bruta × (1 - redução); valor = base × alíquota"),
            {
                "base_bruta": base_bruta,
                "base_calculo": base,
                "aliquota_nominal": aliquota,
                "tratamento": tratamento,
                "regra": resultado.codigo_regra,
            },
            valor_devido,
            "BRL",
            fonte=resultado.fundamento_legal,
            vigencia_regra=(
                f"{resultado.vigencia_inicio} a {resultado.vigencia_fim or 'aberta'}"
            ),
            status_dado=status,
            alerta=resultado.alerta,
        )

    return resultado
