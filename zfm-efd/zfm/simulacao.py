"""Simulacao pos-reforma (SPEC 7.6) e teste de absorcao.

Base: operacoes de 2026 YTD. Ano simulado = meses observados + media mensal nos
meses sem dado (anualizacao). Cada empresa (raiz do CNPJ) e apurada separadamente:
o credito de uma empresa nunca abate o debito de outra; o consolidado e a soma.

Regras (todas parametrizaveis; ver param_aliquotas_cenario, param_regras_entradas,
param_produtos e param_premissas):
  CBS: debito = saidas tributadas × aliq (zero p/ PJ na ZFM, arts. 448/451; exportacao imune)
       credito = entradas creditaveis cujo tratamento e 'tributada' × aliq
       CP art. 450 = saidas incentivadas tributadas × p_cbs_450 (6% ou 2%)
       pagar = debito − credito − CP (com saldo de CP por safra, prazo de 5 anos, art. 452)
  IBS: idem; CP de entrada art. 447 (7,5% S/SE exc. ES; 13,5% demais + ES) e art. 449 (7,5%)
       × fator_cp_entrada; CP art. 450 = p_ibs_450 × parcela do saldo devedor dos incentivados
  ICMS residual (2029-2032) = ICMS atual × fator_icms; credito estimulo e fundos × fator
  IPI: beneficio so para produtos com TIPI >= 6,5% e protegidos (art. 454)
  Contribuicao estadual (art. 457) = receita incentivada × aliquota
Beneficio_pos = carga no regime geral − carga na ZFM;  Delta = Beneficio_pos − Beneficio_hoje.
Carga = tributo pago + tributo embutido nas compras (DECISOES D-016): entrada com aliquota
zero nao e perda (o fornecedor tambem nao cobra o tributo). Assim, beneficio de CBS =
(debito sem excecoes ZFM − debito com excecoes) + CP usado; o saldo credor "normal"
(creditos > debitos) e considerado ressarcivel.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import duckdb
import pandas as pd

from . import beneficio_atual as ba
from . import cfop as _cfop
from . import params

ANOS = list(range(2027, 2034))


# ---------------------------------------------------------------------------
# Percentuais (todos em Parametros > Premissas; nenhum fixo no codigo)
# ---------------------------------------------------------------------------
_PADROES = {"limite_tipi_ipi": 6.5, "p_cbs_450_ipi_zerado": 6.0, "p_cbs_450_demais": 2.0,
            "p_ibs_450_final": 55.0, "p_ibs_450_capital": 75.0, "p_ibs_450_intermediario": 90.25,
            "p_ibs_450_informatica_ou_ce100": 100.0, "cp447_sul_sudeste_exceto_es": 7.5,
            "cp447_demais_e_es": 13.5, "cp449": 7.5}


def percentuais() -> dict[str, float]:
    df = params.carregar("param_premissas")
    return {k: params.premissa_num(k, v, df) for k, v in _PADROES.items()}


def p_ibs_450(tipo_bem: str, ce_100: bool, pc: dict | None = None) -> float:
    pc = pc or percentuais()
    t = (tipo_bem or "").strip().lower()
    if t == "informatica" or ce_100:
        return pc["p_ibs_450_informatica_ou_ce100"] / 100
    chave = {"intermediario": "p_ibs_450_intermediario", "capital": "p_ibs_450_capital"}.get(t, "p_ibs_450_final")
    return pc[chave] / 100


def p_cbs_450(aliq_tipi_2023, produzido_zfm_2024: bool, eh_tic: bool, pc: dict | None = None) -> float:
    pc = pc or percentuais()
    if aliq_tipi_2023 is not None and pd.notna(aliq_tipi_2023) \
            and float(aliq_tipi_2023) < pc["limite_tipi_ipi"] and produzido_zfm_2024 and not eh_tic:
        return pc["p_cbs_450_ipi_zerado"] / 100  # IPI zerado: CP maior
    return pc["p_cbs_450_demais"] / 100


def produtos_com_percentuais(prod: pd.DataFrame) -> pd.DataFrame:
    if prod.empty:
        return prod.assign(p_ibs_450=[], p_cbs_450=[], alerta_ibs=[])
    pc = percentuais()
    out = prod.copy()
    out["p_ibs_450"] = [p_ibs_450(t, c, pc) for t, c in zip(out["tipo_bem"], out["ce_100_em_2023"])]
    out["p_cbs_450"] = [p_cbs_450(a, z, t, pc) for a, z, t in
                        zip(out["aliq_tipi_2023"], out["produzido_zfm_2024"], out["eh_tic"])]
    out["alerta_ibs"] = out["nivel_credito_estimulo"].astype(float) > 100 * out["p_ibs_450"]
    return out


# ---------------------------------------------------------------------------
# Insumos mensais por empresa
# ---------------------------------------------------------------------------
MEDIDAS = ["deb_base_zfm", "deb_base_geral", "cp450_cbs", "base_incent_p_ibs", "ipi_protegido",
           "receita_incent", "cred_cbs_zfm", "cred_ibs_zfm", "cred_base_geral", "cp447_cheio",
           "cp449_cheio", "icms_recolher", "credito_estimulo", "fundos"]


def insumos_mensais(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Uma linha por (raiz, mes) observado com as medidas que a simulacao usa."""
    liquida = params.premissa(None, "base_cbs_ibs", "liquida_sem_tributos") == "liquida_sem_tributos"
    prod = produtos_com_percentuais(params.carregar("param_produtos"))
    pc = percentuais()
    s = con.execute("""
        SELECT raiz, mes, cod_item, categoria_cfop, eh_receita, tipo_operacao, receita_r,
               icms_est_r, pis_r, cofins_r
        FROM v_saidas_dest WHERE estab_no_am""").df()
    partes = []
    if not s.empty:
        s = s.merge(prod[["raiz_cnpj", "cod_item", "incentivado", "p_ibs_450", "p_cbs_450",
                          "aliq_tipi_2023", "aliq_tipi_2026", "ipi_protegido"]],
                    left_on=["raiz", "cod_item"], right_on=["raiz_cnpj", "cod_item"], how="left")
        s["incentivado"] = s["incentivado"].fillna(False).astype(bool) & (s["categoria_cfop"] == "venda_producao")
        base = s["receita_r"] - (s["icms_est_r"] + s["pis_r"] + s["cofins_r"] if liquida else 0)
        tribut_geral = s["eh_receita"].astype(bool) & (s["tipo_operacao"] != "exportacao")
        tribut_zfm = tribut_geral & (s["tipo_operacao"] != "zfm_interna")
        inc = s["incentivado"]
        tipi = s["aliq_tipi_2026"].fillna(s["aliq_tipi_2023"]).astype(float)
        prot = s["ipi_protegido"].fillna(False).astype(bool) & (tipi >= pc["limite_tipi_ipi"])
        m = pd.DataFrame({
            "raiz": s["raiz"], "mes": s["mes"],
            "deb_base_zfm": base.where(tribut_zfm, 0.0),
            "deb_base_geral": base.where(tribut_geral, 0.0),
            "cp450_cbs": (base * s["p_cbs_450"].fillna(0)).where(tribut_zfm & inc, 0.0),
            "base_incent_p_ibs": (base * s["p_ibs_450"].fillna(0)).where(tribut_zfm & inc, 0.0),
            "ipi_protegido": (s["receita_r"] * tipi.fillna(0) / 100).where(
                inc & prot & (s["tipo_operacao"] != "exportacao"), 0.0),
            "receita_incent": s["receita_r"].where(inc & (s["tipo_operacao"] != "exportacao"), 0.0),
        })
        partes.append(m)
    e = con.execute(f"""
        SELECT raiz, mes, origem, sul_sudeste_exceto_es, categoria_cfop,
               CAST(valor AS DOUBLE) AS valor,
               CAST(coalesce(vl_icms, 0) + coalesce(vl_pis, 0) + coalesce(vl_cofins, 0) AS DOUBLE) AS tributos
        FROM v_entradas_item
        WHERE categoria_cfop IN {tuple(_cfop.CATEGORIAS_CREDITAVEIS)}
        UNION ALL
        SELECT raiz, mes, 'servicos', FALSE, 'insumo_servico', CAST(valor AS DOUBLE), 0
        FROM v_entradas_servicos
        WHERE cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)""").df()
    if not e.empty:
        regras = params.carregar("param_regras_entradas").set_index("origem")
        base_e = e["valor"] - (e["tributos"] if liquida else 0)

        def regra(col, padrao):
            return e["origem"].map(regras[col]).fillna(padrao) if col in regras else padrao

        trat_cbs = regra("tratamento_cbs", "tributada")
        trat_ibs = regra("tratamento_ibs", "tributada")
        b447 = regra("base_cp_447", False).astype(bool)
        b449 = regra("base_cp_449", False).astype(bool)
        pct447 = e["sul_sudeste_exceto_es"].fillna(False).astype(bool).map(
            {True: pc["cp447_sul_sudeste_exceto_es"] / 100, False: pc["cp447_demais_e_es"] / 100})
        partes.append(pd.DataFrame({
            "raiz": e["raiz"], "mes": e["mes"],
            "cred_cbs_zfm": base_e.where(trat_cbs == "tributada", 0.0),
            "cred_ibs_zfm": base_e.where(trat_ibs == "tributada", 0.0),
            "cred_base_geral": base_e,
            "cp447_cheio": (base_e * pct447).where(b447 & (trat_ibs == "aliquota_zero"), 0.0),
            "cp449_cheio": (base_e * pc["cp449"] / 100).where(b449 & (e["categoria_cfop"] == "compra_industrializacao"), 0.0),
        }))
    i = con.execute("""
        SELECT a.raiz, a.mes, CAST(a.icms_recolher AS DOUBLE) AS icms_recolher,
               CAST(a.credito_estimulo AS DOUBLE) AS credito_estimulo, CAST(a.fundos AS DOUBLE) AS fundos
        FROM v_apur_icms a JOIN v_estabelecimentos e ON e.cnpj = a.cnpj_estab AND e.no_amazonas""").df()
    if not i.empty:
        partes.append(i)
    if not partes:
        return pd.DataFrame(columns=["raiz", "mes"] + MEDIDAS)
    out = pd.concat(partes, ignore_index=True)
    for c in MEDIDAS:
        if c not in out.columns:
            out[c] = 0.0
    return out.groupby(["raiz", "mes"], as_index=False)[MEDIDAS].sum()


def perfil_anual(mensal: pd.DataFrame, colunas: list[str], chaves: list[str]) -> pd.DataFrame:
    """12 meses por chave: mes observado = valor do mes; mes sem dado = media dos observados.
    Soma anual = media mensal × 12."""
    linhas = []
    for k, g in mensal.groupby(chaves):
        k = k if isinstance(k, tuple) else (k,)
        g = g.set_index("mes")
        media = g[colunas].mean()
        for mes in range(1, 13):
            v = g.loc[mes, colunas] if mes in g.index else media
            linhas.append(dict(zip(chaves, k), mes=mes, observado=mes in g.index, **v.to_dict()))
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Saldo de creditos presumidos por safra
# ---------------------------------------------------------------------------
@dataclass
class Safras:
    prazo_meses: int
    estoque: deque = field(default_factory=deque)  # [indice_mes_origem, valor]

    def adicionar(self, idx: int, valor: float) -> None:
        if valor > 0:
            self.estoque.append([idx, valor])

    def expirar(self, idx: int) -> float:
        exp = 0.0
        while self.estoque and idx - self.estoque[0][0] >= self.prazo_meses:
            exp += self.estoque.popleft()[1]
        return exp

    def usar(self, devido: float) -> float:
        usado = 0.0
        while self.estoque and devido - usado > 1e-9:
            v = min(self.estoque[0][1], devido - usado)
            self.estoque[0][1] -= v
            usado += v
            if self.estoque[0][1] <= 1e-9:
                self.estoque.popleft()
        return usado

    @property
    def saldo(self) -> float:
        return sum(v for _, v in self.estoque)


# ---------------------------------------------------------------------------
# Simulacao
# ---------------------------------------------------------------------------
def _cenarios() -> pd.DataFrame:
    c = params.carregar("param_aliquotas_cenario")
    return c[c["ano"].isin(ANOS)].copy()


def simular(con: duckdb.DuckDBPyConnection, com_teses: bool = False,
            eliminar_intragrupo: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (anual, mensal). Anual: cenario × ano × raiz. Mensal: teste de absorcao."""
    ins = insumos_mensais(con)
    if ins.empty:
        return pd.DataFrame(), pd.DataFrame()
    perfil = perfil_anual(ins, MEDIDAS, ["raiz"])
    hoje = _beneficio_hoje_anual(con, com_teses, eliminar_intragrupo)
    cen = _cenarios()
    prazo = int(params.premissa_num("prazo_cp_anos", 5) * 12)
    teses = params.carregar("param_teses") if com_teses else pd.DataFrame()
    anual, mensal = [], []
    for cenario, cg in cen.groupby("cenario", sort=False):
        cg = cg.set_index("ano")
        for raiz, pr in perfil.groupby("raiz"):
            pr = pr.set_index("mes")
            cp_cbs, cp_ibs = Safras(prazo), Safras(prazo)
            normal_cbs = normal_ibs = 0.0
            idx = 0
            for ano in ANOS:
                if ano not in cg.index:
                    continue
                r = cg.loc[ano]
                a_cbs, a_ibs = (r["aliq_cbs"] or 0) / 100, (r["aliq_ibs"] or 0) / 100
                fator = float(r["fator_icms"]) if pd.notna(r["fator_icms"]) else 0.0
                f_cp = float(r["fator_cp_entrada"]) if pd.notna(r["fator_cp_entrada"]) else 0.0
                aplica450 = bool(r["aplica_cp_450"])
                sem_ipi = str(r["ipi_protegido_override"]).strip().lower() in ("nao", "não", "false")
                a457 = (r["aliq_contrib_art457"] or 0) / 100
                acc = {k: 0.0 for k in (
                    "debito_cbs", "credito_cbs", "cp_cbs_gerado", "cp_cbs_usado", "cp_cbs_expirado",
                    "cbs_pagar", "carga_geral_cbs", "debito_ibs", "credito_ibs", "cp_entrada_gerado",
                    "cp_entrada_usado", "cp_entrada_expirado", "cp_ibs_450", "ibs_pagar",
                    "carga_geral_ibs", "icms_carga_zfm", "icms_carga_geral", "ipi_beneficio",
                    "contrib_457", "teses_beneficio", "meses_saldo_credor")}
                for mes in range(1, 13):
                    v = pr.loc[mes]
                    # ---------------- CBS
                    deb = v["deb_base_zfm"] * a_cbs
                    cred = v["cred_cbs_zfm"] * a_cbs
                    cp_new = v["cp450_cbs"] if aplica450 else 0.0
                    exp_c = cp_cbs.expirar(idx)
                    liq = deb - cred - normal_cbs
                    normal_cbs = max(0.0, -liq)
                    liq = max(0.0, liq)
                    cp_cbs.adicionar(idx, cp_new)
                    usado_c = cp_cbs.usar(liq)
                    cbs_pagar = liq - usado_c
                    # ---------------- IBS
                    deb_i = v["deb_base_zfm"] * a_ibs
                    cred_i = v["cred_ibs_zfm"] * a_ibs
                    cp_ent = (v["cp447_cheio"] + v["cp449_cheio"]) * f_cp if a_ibs > 0 else 0.0
                    exp_i = cp_ibs.expirar(idx)
                    liq_i = deb_i - cred_i - normal_ibs
                    normal_ibs = max(0.0, -liq_i)
                    liq_i = max(0.0, liq_i)
                    cp_ibs.adicionar(idx, cp_ent)
                    usado_i = cp_ibs.usar(liq_i)
                    saldo_dev = liq_i - usado_i
                    share = v["base_incent_p_ibs"] / v["deb_base_zfm"] if v["deb_base_zfm"] else 0.0
                    cp450_ibs = saldo_dev * share if aplica450 else 0.0
                    ibs_pagar = saldo_dev - cp450_ibs
                    # ---------------- ICMS, IPI, art. 457
                    icms_zfm = (v["icms_recolher"] + v["fundos"]) * fator
                    icms_geral = (v["icms_recolher"] + v["credito_estimulo"]) * fator
                    ipi = 0.0 if sem_ipi else v["ipi_protegido"]
                    c457 = v["receita_incent"] * a457
                    tes = _teses_mes(teses, raiz, ano, mes, v["receita_incent"], fator) if com_teses else 0.0
                    saldo_credor = (cp_cbs.saldo + cp_ibs.saldo + normal_cbs + normal_ibs) > 0.005
                    for k, val in (("debito_cbs", deb), ("credito_cbs", cred), ("cp_cbs_gerado", cp_new),
                                   ("cp_cbs_usado", usado_c), ("cp_cbs_expirado", exp_c),
                                   ("cbs_pagar", cbs_pagar),
                                   ("carga_geral_cbs", v["deb_base_geral"] * a_cbs),
                                   ("debito_ibs", deb_i), ("credito_ibs", cred_i),
                                   ("cp_entrada_gerado", cp_ent), ("cp_entrada_usado", usado_i),
                                   ("cp_entrada_expirado", exp_i), ("cp_ibs_450", cp450_ibs),
                                   ("ibs_pagar", ibs_pagar),
                                   ("carga_geral_ibs", v["deb_base_geral"] * a_ibs),
                                   ("icms_carga_zfm", icms_zfm), ("icms_carga_geral", icms_geral),
                                   ("ipi_beneficio", ipi), ("contrib_457", c457), ("teses_beneficio", tes),
                                   ("meses_saldo_credor", 1.0 if saldo_credor else 0.0)):
                        acc[k] += val
                    mensal.append({"cenario": cenario, "ano": ano, "mes": mes, "raiz": raiz,
                                   "observado": bool(v["observado"]),
                                   "cbs_pagar": cbs_pagar, "ibs_pagar": ibs_pagar,
                                   "cp_cbs_gerado": cp_new, "cp_cbs_usado": usado_c,
                                   "cp_cbs_expirado": exp_c, "saldo_cp_cbs": cp_cbs.saldo,
                                   "cp_entrada_gerado": cp_ent, "cp_entrada_usado": usado_i,
                                   "cp_entrada_expirado": exp_i, "saldo_cp_ibs": cp_ibs.saldo,
                                   "saldo_credor_normal_cbs": normal_cbs,
                                   "saldo_credor_normal_ibs": normal_ibs,
                                   "saldo_credor": saldo_credor})
                    idx += 1
                h = hoje.get(raiz, {})
                linha = {"cenario": cenario, "ano": ano, "raiz": raiz, **acc}
                # Carga total = tributo pago + tributo embutido nas compras (DECISOES D-016).
                # Regime geral: debito sem excecoes ZFM. ZFM: debito com excecoes − CP usado.
                linha["carga_zfm_cbs"] = acc["debito_cbs"] - acc["cp_cbs_usado"]
                linha["carga_zfm_ibs"] = acc["debito_ibs"] - acc["cp_entrada_usado"] - acc["cp_ibs_450"]
                linha["beneficio_cbs"] = acc["carga_geral_cbs"] - linha["carga_zfm_cbs"]
                linha["beneficio_cbs_teorico"] = acc["carga_geral_cbs"] - (acc["debito_cbs"] - acc["cp_cbs_gerado"])
                linha["beneficio_ibs"] = acc["carga_geral_ibs"] - linha["carga_zfm_ibs"]
                linha["beneficio_ibs_teorico"] = acc["carga_geral_ibs"] - (
                    acc["debito_ibs"] - acc["cp_entrada_gerado"] - acc["cp_ibs_450"])
                linha["beneficio_icms"] = acc["icms_carga_geral"] - acc["icms_carga_zfm"]
                linha["beneficio_ipi"] = acc["ipi_beneficio"]
                linha["beneficio_contrib_457"] = -acc["contrib_457"]
                linha["beneficio_teses"] = acc["teses_beneficio"]
                linha["beneficio_pos"] = (linha["beneficio_cbs"] + linha["beneficio_ibs"]
                                          + linha["beneficio_icms"] + linha["beneficio_ipi"]
                                          + linha["beneficio_contrib_457"] + linha["beneficio_teses"])
                for t in ba.TRIBUTOS + ["TESES"]:
                    linha[f"hoje_{t.lower()}"] = h.get(t, 0.0)
                linha["beneficio_hoje"] = sum(h.values())
                # Visao so saidas x so entradas (soma = beneficio_pos)
                linha["beneficio_entradas"] = acc["cp_entrada_usado"]
                linha["beneficio_entradas_teorico"] = acc["cp_entrada_gerado"]
                linha["beneficio_saidas"] = linha["beneficio_pos"] - linha["beneficio_entradas"]
                linha["delta"] = linha["beneficio_pos"] - linha["beneficio_hoje"]
                anual.append(linha)
    return pd.DataFrame(anual), pd.DataFrame(mensal)


def _beneficio_hoje_anual(con, com_teses: bool, eliminar_intragrupo: bool) -> dict[str, dict[str, float]]:
    det = ba.calcular(con, com_teses=com_teses, eliminar_intragrupo=eliminar_intragrupo)
    if det.empty:
        return {}
    det = det.assign(tributo=det["tributo"].where(~det["cod_item"].astype(str).str.startswith("TESE:"), "TESES"))
    m = det.groupby(["raiz", "tributo", "mes"], as_index=False)["beneficio"].sum()
    wide = m.pivot_table(index=["raiz", "mes"], columns="tributo", values="beneficio",
                         aggfunc="sum", fill_value=0.0).reset_index()
    cols = [c for c in wide.columns if c not in ("raiz", "mes")]
    # meses observados por empresa (inclusive meses sem beneficio)
    obs = con.execute("""SELECT DISTINCT raiz, month(dt_ini) AS mes FROM arquivos
                         WHERE ativo AND tipo = 'ICMS_IPI' AND year(dt_ini) = ?""",
                      [int(params.premissa_num("ano_base", 2026))]).df()
    wide = obs.merge(wide, on=["raiz", "mes"], how="left").fillna(0.0)
    p = perfil_anual(wide, cols, ["raiz"])
    tot = p.groupby("raiz")[cols].sum()
    return {r: tot.loc[r].to_dict() for r in tot.index}


def _teses_mes(teses: pd.DataFrame, raiz: str, ano: int, mes: int, receita: float, fator_icms: float) -> float:
    if teses.empty:
        return 0.0
    total = 0.0
    geral = ba._aliq_geral()
    for t in teses.itertuples():
        if t.raiz_cnpj not in ("", "todas", raiz) or not ba.em_vigencia(t, ano, mes):
            continue
        trib = t.tributo.upper()
        if trib in ("PIS", "COFINS"):
            continue  # tributos extintos em 2027: tese perde efeito prospectivo
        v = ba.valor_tese(t, receita, geral)
        total += v * fator_icms if trib == "ICMS" else v
    return total


def ponte(anual: pd.DataFrame, cenario: str, ano: int, raizes: list[str] | None = None) -> pd.DataFrame:
    """Waterfall do beneficio de hoje ao pos-reforma, por tributo."""
    a = anual[(anual.cenario == cenario) & (anual.ano == ano)]
    if raizes is not None:
        a = a[a.raiz.isin(raizes)]
    s = a.sum(numeric_only=True)
    passos = [("Benefício hoje", s.get("beneficio_hoje", 0.0), "absolute"),
              ("− IPI de hoje", -s.get("hoje_ipi", 0.0), "relative"),
              ("− PIS de hoje", -s.get("hoje_pis", 0.0), "relative"),
              ("− COFINS de hoje", -s.get("hoje_cofins", 0.0), "relative"),
              ("− ICMS de hoje", -s.get("hoje_icms", 0.0), "relative"),
              ("− Teses de hoje", -s.get("hoje_teses", 0.0), "relative"),
              ("+ CBS", s.get("beneficio_cbs", 0.0), "relative"),
              ("+ IBS (saídas)", s.get("beneficio_ibs", 0.0) - s.get("cp_entrada_usado", 0.0), "relative"),
              ("+ CP de entrada 447/449 (entradas)", s.get("cp_entrada_usado", 0.0), "relative"),
              ("+ ICMS residual", s.get("beneficio_icms", 0.0), "relative"),
              ("+ IPI protegido", s.get("beneficio_ipi", 0.0), "relative"),
              ("− Contribuição art. 457", s.get("beneficio_contrib_457", 0.0), "relative"),
              ("+ Teses pós-reforma", s.get("beneficio_teses", 0.0), "relative"),
              ("Benefício pós-reforma", s.get("beneficio_pos", 0.0), "total")]
    return pd.DataFrame(passos, columns=["etapa", "valor", "medida"])
