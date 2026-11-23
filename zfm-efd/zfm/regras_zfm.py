"""Motor juridico da ZFM por operacao (LC 214/2025, arts. 440-455): calculo, requisitos e memoria.

Valores monetarios em Decimal. Percentuais e vigencias de param_regras_legais (zfm/regras.py);
aliquotas de CBS/IBS/IPI sao premissas de simulacao informadas pelo usuario (nunca fixas no codigo).
Cada funcao devolve um Resultado com os valores, os requisitos (atendido / nao atendido / nao
comprovado), o status de elegibilidade, a formula, o fundamento e uma memoria de calculo legivel.
Nada e presumido: requisito sem informacao fica 'nao comprovado' (None).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from . import params, regras

D = Decimal
ZERO = D("0")
CEM = D("100")

ELEGIVEL = "Elegível"
NAO_ELEGIVEL = "Não elegível"
POTENCIAL = "Potencialmente elegível - depende de validação"
INSUFICIENTE = "Informação insuficiente para determinar"

SUL_SUDESTE_EXCETO_ES = {"MG", "RJ", "SP", "PR", "SC", "RS"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE",
       "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


def q2(v) -> Decimal:
    return D(str(v)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _pct(v) -> Decimal:
    return D(str(v)) / CEM


def _fmt(v: Decimal) -> str:
    s = f"{q2(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fp(v) -> str:
    return f"{D(str(v)).normalize():f}".replace(".", ",") + "%"


@dataclass
class Resultado:
    cenario: str
    fundamento: str
    valores: dict[str, Decimal] = field(default_factory=dict)
    requisitos: dict[str, bool | None] = field(default_factory=dict)  # True atendido, False nao, None nao comprovado
    insuficientes: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return status_elegibilidade(self.requisitos, self.insuficientes)

    @property
    def confianca(self) -> str:
        return {ELEGIVEL: "alta", POTENCIAL: "média", INSUFICIENTE: "baixa", NAO_ELEGIVEL: "alta"}[self.status]

    def memoria(self) -> str:
        ok = [k for k, v in self.requisitos.items() if v is True]
        nao = [k for k, v in self.requisitos.items() if v is False]
        pend = [k for k, v in self.requisitos.items() if v is None]
        partes = [f"Cenário {self.cenario} — {self.status} (confiança {self.confianca})."]
        if ok:
            partes.append("Requisitos atendidos: " + "; ".join(ok) + ".")
        if nao:
            partes.append("Requisitos NÃO atendidos: " + "; ".join(nao) + ". O incentivo não se aplica (regra geral, "
                          "art. 453).")
        if pend:
            partes.append("Requisitos NÃO comprovados: " + "; ".join(pend) + ". O benefício abaixo é estimativa, "
                          "sujeito a risco de recuperação.")
        if self.insuficientes:
            partes.append("Dados ausentes: " + "; ".join(self.insuficientes) + ".")
        if self.formulas:
            partes.append("Cálculo: " + " | ".join(self.formulas) + ".")
        partes.append("Fundamento: " + self.fundamento + ".")
        partes += self.observacoes
        return " ".join(partes)


def status_elegibilidade(requisitos: dict[str, bool | None], insuficientes: list[str] | None = None) -> str:
    if any(v is False for v in requisitos.values()):
        return NAO_ELEGIVEL
    if insuficientes:
        return INSUFICIENTE
    if any(v is None for v in requisitos.values()):
        return POTENCIAL
    return ELEGIVEL


def _regra_pct(codigo: str, data: _dt.date | None = None) -> Decimal | None:
    """Percentual da regra legal (em %), ou None se nao parametrizada/nao vigente na data."""
    r = regras.regra(codigo)
    if r is None or r.percentual is None:
        return None
    if data is not None and not r.vigente_em(data):
        return None
    return D(str(r.percentual))


def _exige(res: Resultado, codigo: str, data: _dt.date | None) -> Decimal:
    p = _regra_pct(codigo, data)
    if p is None:
        r = regras.regra(codigo)
        motivo = "não parametrizada" if r is None or r.percentual is None else \
            f"fora da vigência ({r.inicio or '—'} a {r.fim or '—'}, {r.status})"
        res.observacoes.append(f"Regra {codigo} {motivo}: componente não aplicado.")
        return ZERO
    return p


# ---------------------------------------------------------------------------
# Acrescimos legais (art. 29, § 2º) — parametrizados; vazio = pendente (nao calculados)
# ---------------------------------------------------------------------------
def acrescimos(principal: Decimal, inicio: _dt.date, fim: _dt.date) -> tuple[Decimal, Decimal, str]:
    juros = params.premissa_num("taxa_juros_acrescimos_mes", -1)
    multa = params.premissa_num("multa_acrescimos_pct", -1)
    if juros < 0 or multa < 0:
        return ZERO, ZERO, "acréscimos pendentes de parametrização (Premissas: taxa_juros_acrescimos_mes, multa_acrescimos_pct)"
    meses = max(0, (fim.year - inicio.year) * 12 + fim.month - inicio.month)
    j = q2(principal * _pct(juros) * meses)
    m = q2(principal * _pct(multa))
    return j, m, f"juros {_fp(juros)} a.m. × {meses} meses + multa {_fp(multa)}"


# ---------------------------------------------------------------------------
# Cenario 1 — importacao (arts. 443 e 444)
# ---------------------------------------------------------------------------
def art443_importacao(base_ibs: Decimal, base_cbs: Decimal, aliq_ibs: Decimal, aliq_cbs: Decimal,
                      data: _dt.date, requisitos: dict[str, bool | None]) -> Resultado:
    res = Resultado("C1a", "LC 214/2025, art. 443", requisitos=dict(requisitos))
    ibs, cbs = q2(base_ibs * _pct(aliq_ibs)), q2(base_cbs * _pct(aliq_cbs))
    suspensa = res.status != NAO_ELEGIVEL and regras.regra("ART443_SUSPENSAO") is not None \
        and regras.regra("ART443_SUSPENSAO").vigente_em(data)
    res.valores = {"ibs_suspenso": ibs if suspensa else ZERO, "cbs_suspensa": cbs if suspensa else ZERO,
                   "desembolso_inicial": ZERO if (suspensa and res.status == ELEGIVEL) else ibs + cbs,
                   "ibs_importacao": ibs, "cbs_importacao": cbs}
    res.formulas.append(f"IBS suspenso = {_fmt(base_ibs)} × {_fp(aliq_ibs)} = {_fmt(ibs)}")
    res.formulas.append(f"CBS suspensa = {_fmt(base_cbs)} × {_fp(aliq_cbs)} = {_fmt(cbs)}")
    if res.status != ELEGIVEL:
        res.observacoes.append("Desembolso inicial zero só com a suspensão confirmada; até lá o valor fica como estimativa.")
    return res


def art443_conversao(data_entrada: _dt.date, data_evento: _dt.date, consumido: bool = False,
                     data_depreciacao_integral: _dt.date | None = None) -> tuple[bool, str]:
    """Suspensao convertida em isencao: bem consumido/incorporado na producao, ou ativo com depreciacao integral ou
    permanencia de N meses (ART443_PRAZO_MESES), o que ocorrer primeiro."""
    prazo = int(_regra_pct("ART443_PRAZO_MESES") or 0)
    if consumido:
        return True, "consumido ou incorporado ao processo produtivo na ZFM"
    meses = (data_evento.year - data_entrada.year) * 12 + data_evento.month - data_entrada.month \
        - (1 if data_evento.day < data_entrada.day else 0)
    if prazo and meses >= prazo:
        return True, f"permanência de {meses} meses (prazo de {prazo})"
    if data_depreciacao_integral and data_evento >= data_depreciacao_integral:
        return True, "depreciação integral"
    return False, f"{meses} meses na ZFM (prazo de {prazo}); suspensão ainda não convertida"


def art443_saida_antes(ibs_suspenso: Decimal, cbs_suspensa: Decimal, data_desembaraco: _dt.date,
                       data_saida: _dt.date) -> Resultado:
    """Bem sai da ZFM antes da conversao: tributos suspensos + acrescimos; credito ordinario so do principal."""
    res = Resultado("C1a", "LC 214/2025, art. 443; art. 29, § 2º (acréscimos)",
                    requisitos={"permanência na ZFM até a conversão": False})
    principal = q2(ibs_suspenso + cbs_suspensa)
    j, m, txt = acrescimos(principal, data_desembaraco, data_saida)
    res.valores = {"principal": principal, "juros": j, "multa": m, "total_recolher": principal + j + m,
                   "credito_ordinario_apos_pagamento": principal}
    res.formulas += [f"principal = IBS {_fmt(ibs_suspenso)} + CBS {_fmt(cbs_suspensa)} = {_fmt(principal)}",
                     f"acréscimos: {txt}", f"crédito ordinário = principal pago = {_fmt(principal)} (sem acréscimos)"]
    return res


def art444(base_ibs: Decimal, base_cbs: Decimal, aliq_ibs: Decimal, aliq_cbs: Decimal, data: _dt.date,
           regime_regular: bool, requisitos: dict[str, bool | None]) -> Resultado:
    res = Resultado("C1b", "LC 214/2025, art. 444", requisitos=dict(requisitos))
    p = _exige(res, "ART444_CP_IBS", data)
    nominal = q2(base_ibs * _pct(aliq_ibs))
    cp = q2(base_ibs * _pct(aliq_ibs) * _pct(p)) if res.status != NAO_ELEGIVEL else ZERO
    cbs = q2(base_cbs * _pct(aliq_cbs))
    res.valores = {"ibs_nominal": nominal, "credito_presumido_ibs": cp, "ibs_recolher_importacao": nominal - cp,
                   "cbs_importacao": cbs, "credito_ordinario_ibs": nominal if regime_regular else ZERO,
                   "credito_ordinario_cbs": cbs if regime_regular else ZERO,
                   "valor_sujeito_a_recuperacao": cp}
    res.formulas += [f"IBS nominal = {_fmt(base_ibs)} × {_fp(aliq_ibs)} = {_fmt(nominal)}",
                     f"crédito presumido = {_fmt(base_ibs)} × {_fp(aliq_ibs)} × {_fp(p)} = {_fmt(cp)}",
                     f"IBS a recolher na importação = {_fmt(nominal - cp)}",
                     f"CBS = {_fmt(base_cbs)} × {_fp(aliq_cbs)} = {_fmt(cbs)}"]
    res.observacoes.append("Recuperação (crédito presumido + acréscimos desde a importação) se a revenda não for "
                           "presencial, sem comprovação de ingresso ou em revenda/transferência para fora da ZFM.")
    return res


# ---------------------------------------------------------------------------
# Cenario 2 — aquisicao de outra UF (arts. 445 a 447)
# ---------------------------------------------------------------------------
def percentual_art447(uf_origem: str, data: _dt.date) -> tuple[str, Decimal | None]:
    uf = (uf_origem or "").upper()
    if uf not in UFS or uf == "AM":
        return "", None
    cod = "ART447_SS" if uf in SUL_SUDESTE_EXCETO_ES else "ART447_DEMAIS"
    return cod, _regra_pct(cod, data)


def art445_447(base: Decimal, aliq_ibs: Decimal, aliq_cbs: Decimal, uf_origem: str, data: _dt.date,
               industria_incentivada: bool, utilizacao_zfm: bool, regime: str,
               requisitos: dict[str, bool | None], valor_agregado_encomenda: Decimal | None = None) -> Resultado:
    """regime: 'regular' ou 'simples'. Na industrializacao por encomenda, o credito presumido incide so sobre o
    valor agregado (valor_agregado_encomenda)."""
    res = Resultado("C2a" if industria_incentivada else ("C2c" if regime == "simples" else "C2b"),
                    "LC 214/2025, arts. 445, 446 e 447", requisitos=dict(requisitos))
    nao = res.status == NAO_ELEGIVEL
    ibs_saida = ZERO if not nao else q2(base * _pct(aliq_ibs))
    cbs_saida = ZERO if not nao else q2(base * _pct(aliq_cbs))
    beneficio = q2(base * (_pct(aliq_ibs) + _pct(aliq_cbs))) if not nao else ZERO
    # art. 446: IBS na entrada no AM
    if nao or (industria_incentivada and utilizacao_zfm):
        ibs_entrada = ZERO
        res.formulas.append("IBS na entrada = 0 (indústria incentivada com utilização na ZFM)" if not nao else
                            "regra geral: sem alíquota zero")
    else:
        p446 = _exige(res, "ART446_IBS_ENTRADA", data)
        ibs_entrada = q2(base * _pct(aliq_ibs) * _pct(p446))
        res.formulas.append(f"IBS na entrada (art. 446) = {_fmt(base)} × {_fp(aliq_ibs)} × {_fp(p446)} = {_fmt(ibs_entrada)}")
    # art. 447: credito presumido do adquirente regular
    cod, p447 = percentual_art447(uf_origem, data)
    base_cp = valor_agregado_encomenda if valor_agregado_encomenda is not None else base
    if nao or regime != "regular" or p447 is None:
        cp = ZERO
        if not nao and regime != "regular":
            res.formulas.append("crédito presumido do art. 447 = 0 (adquirente fora do regime regular)")
        elif not nao and p447 is None:
            res.observacoes.append(f"Crédito presumido do art. 447 não aplicado: UF {uf_origem or '?'} inválida ou "
                                   f"regra {cod or 'ART447'} fora da vigência/não parametrizada.")
    else:
        cp = q2(base_cp * _pct(p447))
        res.formulas.append(f"crédito presumido (art. 447, origem {uf_origem}) = {_fmt(base_cp)} × {_fp(p447)} = {_fmt(cp)}"
                            + (" (só o valor agregado: industrialização por encomenda)"
                               if valor_agregado_encomenda is not None else ""))
    res.valores = {"ibs_saida_fornecedor": ibs_saida, "cbs_saida_fornecedor": cbs_saida,
                   "beneficio_bruto_saida": beneficio, "ibs_entrada_art446": ibs_entrada,
                   "credito_ordinario_ibs_entrada": ibs_entrada if regime == "regular" else ZERO,
                   "credito_presumido_ibs_art447": cp,
                   "valor_sujeito_a_estorno": cp if requisitos.get("ingresso na ZFM comprovado") is not True else ZERO}
    res.observacoes.append("O benefício bruto da saída não é, por si, ganho do fornecedor ou do adquirente: depende do "
                           "repasse de preço (ver motor de preços). Sem comprovação de ingresso, o crédito presumido é "
                           "estornado com acréscimos.")
    return res


# ---------------------------------------------------------------------------
# Cenario 3 — ZFM -> ZFM, intermediario entre industrias incentivadas (arts. 448 e 449)
# ---------------------------------------------------------------------------
def art448_449(base: Decimal, data: _dt.date, requisitos: dict[str, bool | None],
               valor_agregado_encomenda: Decimal | None = None) -> Resultado:
    res = Resultado("C3a", "LC 214/2025, arts. 448 e 449 (sem o art. 450 sobre a mesma operação)",
                    requisitos=dict(requisitos))
    p = _exige(res, "ART449_CP_IBS", data)
    base_cp = valor_agregado_encomenda if valor_agregado_encomenda is not None else base
    cp = q2(base_cp * _pct(p)) if res.status != NAO_ELEGIVEL else ZERO
    res.valores = {"ibs_operacao": ZERO, "cbs_operacao": ZERO, "credito_presumido_ibs_art449": cp,
                   "credito_presumido_art450": ZERO}
    res.formulas.append(f"IBS/CBS da operação = 0 (art. 448); crédito presumido (art. 449) = {_fmt(base_cp)} × "
                        f"{_fp(p)} = {_fmt(cp)}")
    if requisitos.get("bem incorporado/consumido na produção de bem final") is None:
        res.observacoes.append("Depende de comprovação produtiva (Bloco K ou controle de produção).")
    return res


# ---------------------------------------------------------------------------
# Cenario 4 — venda de produto industrializado na ZFM (art. 450)
# ---------------------------------------------------------------------------
FAIXAS = {"55": ("ART450_IBS_FINAL", "bem de consumo final"), "75": ("ART450_IBS_CAPITAL", "bem de capital"),
          "90_25": ("ART450_IBS_INTERMEDIARIO", "bem intermediário"),
          "100_informatica": ("ART450_IBS_INFORMATICA", "bem de informática"),
          "100_ce": ("ART450_IBS_CE100", "crédito estímulo de 100% em 31/12/2023")}


def art450_ibs(debitos: dict[str, Decimal], debitos_nao_elegiveis: Decimal, creditos: Decimal, data: _dt.date,
               ajustes_debito: dict[str, Decimal] | None = None, ajustes_credito: dict[str, Decimal] | None = None
               ) -> Resultado:
    """Credito presumido de IBS sobre o SALDO DEVEDOR do periodo, por faixa. Creditos alocados as faixas na
    proporcao dos debitos (criterio 'proporcional_debito', demonstrado). Nunca sobre a receita."""
    res = Resultado("C4", "LC 214/2025, art. 450 (§ 6º, na redação da LC 227/2026 — conferir)")
    ajd, ajc = ajustes_debito or {}, ajustes_credito or {}
    total_deb = sum(debitos.values(), ZERO) + debitos_nao_elegiveis
    cp_total, sd_total = ZERO, ZERO
    for k, deb in debitos.items():
        cod, nome = FAIXAS[k]
        p = _exige(res, cod, data)
        cred_aloc = q2(creditos * deb / total_deb) if total_deb > 0 else ZERO
        sd = max(ZERO, deb - cred_aloc + ajd.get(k, ZERO) - ajc.get(k, ZERO))
        cp = q2(sd * _pct(p))
        res.valores[f"debitos_{k}"], res.valores[f"creditos_alocados_{k}"] = deb, cred_aloc
        res.valores[f"saldo_devedor_{k}"], res.valores[f"credito_presumido_{k}"] = sd, cp
        res.formulas.append(f"{nome}: saldo {_fmt(deb)} − créditos alocados {_fmt(cred_aloc)} = {_fmt(sd)}; "
                            f"CP = {_fmt(sd)} × {_fp(p)} = {_fmt(cp)}")
        cp_total += cp
        sd_total += sd
    cred_ne = q2(creditos * debitos_nao_elegiveis / total_deb) if total_deb > 0 else ZERO
    sd_ne = max(ZERO, debitos_nao_elegiveis - cred_ne)
    res.valores.update({"saldo_devedor_nao_elegivel": sd_ne, "saldo_devedor_total": sd_total + sd_ne,
                        "credito_presumido_ibs_total": cp_total,
                        "ibs_liquido_apos_cp": sd_total + sd_ne - cp_total})
    res.formulas.append(f"IBS após o crédito presumido = {_fmt(sd_total + sd_ne)} − {_fmt(cp_total)} = "
                        f"{_fmt(sd_total + sd_ne - cp_total)}")
    return res


def art450_cbs(valor_operacao: Decimal, data: _dt.date, enquadrado_art454: bool, operacao_tributada: bool,
               operacao_art448: bool, requisitos: dict[str, bool | None]) -> Resultado:
    """Credito presumido de CBS por item/documento, sobre o VALOR DA OPERACAO (nunca sobre saldo devedor)."""
    res = Resultado("C4", "LC 214/2025, art. 450 (CBS)", requisitos=dict(requisitos))
    res.requisitos["operação tributada (não isenta, alíquota zero, suspensa ou diferida)"] = operacao_tributada
    res.requisitos["não é operação do art. 448"] = not operacao_art448
    cod = "ART450_CBS_454" if enquadrado_art454 else "ART450_CBS_DEMAIS"
    p = _exige(res, cod, data)
    cp = q2(valor_operacao * _pct(p)) if res.status != NAO_ELEGIVEL else ZERO
    res.valores = {"credito_presumido_cbs": cp, "percentual": p}
    res.formulas.append(f"CP de CBS = {_fmt(valor_operacao)} × {_fp(p)} = {_fmt(cp)} "
                        f"({'produto do art. 454' if enquadrado_art454 else 'demais produtos'})")
    return res


# ---------------------------------------------------------------------------
# Cenario 5 — venda dentro da ZFM de bem nacional ou servico prestado na ZFM (art. 451)
# ---------------------------------------------------------------------------
def art451(base: Decimal, aliq_ibs: Decimal, aliq_cbs: Decimal, requisitos: dict[str, bool | None],
           creditos_cbs_antecedentes: Decimal = ZERO, servico: bool = False) -> Resultado:
    res = Resultado("C5S" if servico else "C5M", "LC 214/2025, art. 451", requisitos=dict(requisitos))
    nao = res.status == NAO_ELEGIVEL
    cbs = q2(base * _pct(aliq_cbs)) if nao else ZERO
    ibs = q2(base * _pct(aliq_ibs))
    beneficio = ZERO if nao else q2(base * _pct(aliq_cbs))
    res.valores = {"cbs_operacao": cbs, "ibs_operacao": ibs, "beneficio_cbs": beneficio,
                   "saldo_creditos_cbs_mantidos": ZERO if nao else creditos_cbs_antecedentes}
    res.formulas += [f"CBS = {'0 (alíquota zero)' if not nao else _fmt(cbs)}",
                     f"IBS = {_fmt(base)} × {_fp(aliq_ibs)} = {_fmt(ibs)}",
                     f"benefício de CBS = {_fmt(base)} × {_fp(aliq_cbs)} = {_fmt(beneficio)}"]
    if servico and requisitos.get("local físico da prestação na ZFM comprovado") is None:
        res.observacoes.append("Potencialmente elegível — local físico não comprovado.")
    return res


# ---------------------------------------------------------------------------
# Cenario 6 — IPI (arts. 454 e 455)
# ---------------------------------------------------------------------------
def art454(aliq_tipi_2023: Decimal | None, industrializado_2024: bool | None, projeto_cas_2022_2025: bool | None,
           tic_excluido: bool | None, excluido_art441: bool | None, base_ipi: Decimal, ano: int) -> Resultado:
    res = Resultado("C6", "LC 214/2025, art. 454")
    lim = _regra_pct("ART454_LIMITE_TIPI")
    if aliq_tipi_2023 is None:
        res.insuficientes.append("alíquota da TIPI em 31/12/2023")
        res.requisitos["TIPI em 31/12/2023 abaixo do limite"] = None
    else:
        res.requisitos["TIPI em 31/12/2023 abaixo do limite"] = lim is not None and aliq_tipi_2023 < lim
    if industrializado_2024 is True or projeto_cas_2022_2025 is True:
        res.requisitos["industrializado na ZFM em 2024 ou projeto CAS 2022–2025"] = True
    elif industrializado_2024 is False and projeto_cas_2022_2025 is False:
        res.requisitos["industrializado na ZFM em 2024 ou projeto CAS 2022–2025"] = False
    else:
        res.requisitos["industrializado na ZFM em 2024 ou projeto CAS 2022–2025"] = None
    res.requisitos["não é TIC excluído da redução"] = None if tic_excluido is None else not tic_excluido
    res.requisitos["não excluído do regime (art. 441)"] = None if excluido_art441 is None else not excluido_art441
    vig = regras.fator("ART454_LIMITE_TIPI", ano) > 0
    ipi_hist = q2(base_ipi * _pct(aliq_tipi_2023 or 0))
    zera = res.status in (ELEGIVEL, POTENCIAL) and vig
    res.valores = {"ipi_historico": ipi_hist, "aliquota_ipi_futura": ZERO if zera else D(str(aliq_tipi_2023 or 0)),
                   "ipi_futuro": ZERO if zera else ipi_hist, "beneficio_ipi": ipi_hist if zera else ZERO}
    res.formulas.append(f"IPI histórico = {_fmt(base_ipi)} × {_fp(aliq_tipi_2023 or 0)} = {_fmt(ipi_hist)}; "
                        f"IPI futuro ({ano}) = {_fmt(res.valores['ipi_futuro'])}")
    if zera:
        res.observacoes.append("Produto também pode ter o crédito presumido de CBS de 6% do art. 450, se atender aos "
                               "requisitos desse artigo.")
    return res


def art455(alternativa: str, valor_operacao: Decimal, similar_nacional: bool | None, data: _dt.date) -> Resultado:
    res = Resultado("C6", "LC 214/2025, art. 455")
    res.requisitos["sem similar nacional"] = None if similar_nacional is None else not similar_nacional
    if alternativa == "A_cp_cbs_6":
        p = _exige(res, "ART455_CP_CBS", data)
        res.valores = {"credito_presumido_cbs": q2(valor_operacao * _pct(p)) if res.status != NAO_ELEGIVEL else ZERO}
        res.formulas.append(f"Alternativa A: CP de CBS = {_fmt(valor_operacao)} × {_fp(p)}")
    elif alternativa == "B_ipi_6_5":
        p = _exige(res, "ART455_IPI_MIN", data)
        res.valores = {"aliquota_ipi_minima": p}
        res.formulas.append(f"Alternativa B: alíquota de IPI de no mínimo {_fp(p)}")
    else:
        res.insuficientes.append("alternativa do art. 455 (A ou B) não definida")
    res.observacoes.append("Alternativas A e B não são cumulativas; dependem de ato do Poder Executivo.")
    return res


# ---------------------------------------------------------------------------
# Motor de precos (IBS/CBS/IPI cobrados "por fora")
# ---------------------------------------------------------------------------
def precos(premissa: str, valor: Decimal, aliq_ibs: Decimal, aliq_cbs: Decimal, aliq_ipi: Decimal = ZERO,
           aliq_is: Decimal = ZERO, outros_pct: Decimal = ZERO, repasse_pct: Decimal = CEM,
           preco_liquido_atual: Decimal | None = None) -> dict[str, Decimal]:
    """premissa: 'liquido_constante' (valor = preco liquido B), 'bruto_constante' (valor = preco bruto G) ou
    'repasse_parcial' (valor = preco atual; o preco bruto sobe repasse_pct % dos tributos novos).
    Tributos por fora: bruto = liquido × (1 + soma das aliquotas). Nao usa a logica 'por dentro' do ICMS."""
    soma = _pct(aliq_ibs) + _pct(aliq_cbs) + _pct(aliq_ipi) + _pct(aliq_is) + _pct(outros_pct)
    if premissa == "bruto_constante":
        liquido = q2(valor / (1 + soma))
    elif premissa == "repasse_parcial":
        # preco bruto alvo = preco atual × (1 + repasse × soma das aliquotas); 100% = liquido constante,
        # 0% = bruto constante
        base = preco_liquido_atual if preco_liquido_atual is not None else valor
        liquido = q2(base * (1 + _pct(repasse_pct) * soma) / (1 + soma))
    else:
        liquido = q2(valor)
    ibs, cbs = q2(liquido * _pct(aliq_ibs)), q2(liquido * _pct(aliq_cbs))
    ipi, is_ = q2(liquido * _pct(aliq_ipi)), q2(liquido * _pct(aliq_is))
    outros = q2(liquido * _pct(outros_pct))
    return {"preco_liquido": liquido, "ibs": ibs, "cbs": cbs, "ipi": ipi, "imposto_seletivo": is_, "outros": outros,
            "preco_bruto": liquido + ibs + cbs + ipi + is_ + outros}
