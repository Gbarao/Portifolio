"""Motor To Be (2027-2033) e diferenca de carga (etapas 7 e 8).

Diferenca(empresa, ano, tributo) = carga To Be − carga As Is
    positivo = aumento de carga (perda); negativo = reducao (ganho).

As Is: lido da apuracao (zfm/as_is.py), anualizado (YTD ÷ meses × 12).
To Be, mes a mes, por unidade de apuracao (premissa nivel_apuracao_cbs_ibs: raiz ou
estabelecimento), sobre a BASE DE OPERACOES (v_base_operacoes) de 2026 anualizada:
  CBS: debito = saidas tributadas × aliq (zero p/ PJ na ZFM, arts. 448/451; exportacao sem debito)
       credito = entradas creditaveis com tratamento 'tributada' (art. 445: aliquota zero;
       art. 443: importacao suspensa) ; CP art. 450 = saidas incentivadas TRIBUTADAS × 6%/2%
       a recolher = max(0, debito − creditos − CP − saldo anterior utilizavel)
  IBS: idem; CP de entrada art. 447 (7,5% S/SE exc. ES; 13,5% demais + ES) e art. 449 (7,5%)
       × fator de transicao; CP art. 450 = % do produto × saldo devedor atribuivel aos
       incentivados; ordem de deducao pela premissa ordem_deducao_ibs
  ICMS residual = ICMS As Is (apuracao) × fator do ano ; IPI proprio = IPI As Is × fator_ipi_proprio
  Contribuicao estadual (art. 457) = receita incentivada × aliquota
Teste de absorcao: credito presumido por safra (mes de origem), so abate a propria
unidade, sem ressarcimento, vence em prazo_cp_anos (art. 452). Saldo credor "normal"
(creditos > debitos) e carregado para os meses seguintes.
Duas metricas separadas: carga propria (acima) e vantagem competitiva do IPI
(IPI que o concorrente de fora pagava sobre os produtos incentivados e deixa de pagar).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import duckdb
import pandas as pd

from . import as_is as _as_is
from . import cfop as _cfop
from . import params
from .filtros import TODOS, Filtro

ANOS = list(range(2027, 2034))


# ---------------------------------------------------------------------------
# Percentuais: tabela de regras legais versionada (Parametros > Regras legais); nada fixo no codigo
# ---------------------------------------------------------------------------
_REGRA = {"limite_tipi_ipi": "ART454_LIMITE_TIPI", "p_cbs_450_ipi_zerado": "ART450_CBS_454",
          "p_cbs_450_demais": "ART450_CBS_DEMAIS", "p_ibs_450_final": "ART450_IBS_FINAL",
          "p_ibs_450_capital": "ART450_IBS_CAPITAL", "p_ibs_450_intermediario": "ART450_IBS_INTERMEDIARIO",
          "p_ibs_450_informatica": "ART450_IBS_INFORMATICA", "p_ibs_450_ce100": "ART450_IBS_CE100",
          "cp447_sul_sudeste_exceto_es": "ART447_SS", "cp447_demais_e_es": "ART447_DEMAIS",
          "cp449": "ART449_CP_IBS", "cp444": "ART444_CP_IBS", "ibs_entrada_446": "ART446_IBS_ENTRADA"}
FAIXAS_450 = {"55": "ART450_IBS_FINAL", "75": "ART450_IBS_CAPITAL", "90_25": "ART450_IBS_INTERMEDIARIO",
              "100": "ART450_IBS_INFORMATICA"}


def percentuais() -> dict[str, float]:
    """Percentuais cadastrados (em %). Regra sem percentual cadastrado vale 0 (e gera alerta)."""
    from . import regras
    t = regras.carregar()
    return {k: (regras.pct(c, t) or 0.0) for k, c in _REGRA.items()}


def faixa_450(tipo_bem: str, ce_100: bool) -> str:
    t = (tipo_bem or "").strip().lower()
    if t == "informatica" or ce_100:
        return "100"
    return {"intermediario": "90_25", "capital": "75"}.get(t, "55")


def p_ibs_450(tipo_bem: str, ce_100: bool, pc: dict | None = None) -> float:
    pc = pc or percentuais()
    t = (tipo_bem or "").strip().lower()
    if t == "informatica":
        return pc["p_ibs_450_informatica"] / 100
    if ce_100:
        return pc["p_ibs_450_ce100"] / 100
    chave = {"intermediario": "p_ibs_450_intermediario", "capital": "p_ibs_450_capital"}.get(t, "p_ibs_450_final")
    return pc[chave] / 100


def enquadrado_art454(aliq_tipi_2023, produzido_zfm_2024: bool, eh_tic: bool, projeto_cas: bool = False,
                      pc: dict | None = None) -> bool:
    """Art. 454: TIPI de 31/12/2023 abaixo do limite + (industrializado na ZFM em 2024 OU projeto aprovado pelo
    CAS na janela do art. 454) + nao ser TIC excluido da reducao."""
    pc = pc or percentuais()
    if aliq_tipi_2023 is None or pd.isna(aliq_tipi_2023):
        return False
    return float(aliq_tipi_2023) < pc["limite_tipi_ipi"] and (produzido_zfm_2024 or projeto_cas) and not eh_tic


def p_cbs_450(aliq_tipi_2023, produzido_zfm_2024: bool, eh_tic: bool, pc: dict | None = None,
              projeto_cas: bool = False) -> float:
    pc = pc or percentuais()
    if enquadrado_art454(aliq_tipi_2023, produzido_zfm_2024, eh_tic, projeto_cas, pc):
        return pc["p_cbs_450_ipi_zerado"] / 100  # produto do art. 454: CP de CBS maior
    return pc["p_cbs_450_demais"] / 100


def produtos_com_percentuais(prod: pd.DataFrame) -> pd.DataFrame:
    if prod.empty:
        return prod.assign(p_ibs_450=[], p_cbs_450=[], alerta_ibs=[], faixa_450=[], art454=[])
    pc = percentuais()
    out = prod.copy()
    cas = out["projeto_cas_2022_2025"].astype(str).str.lower().eq("sim") if "projeto_cas_2022_2025" in out \
        else pd.Series(False, index=out.index)
    out["p_ibs_450"] = [p_ibs_450(t, c, pc) for t, c in zip(out["tipo_bem"], out["ce_100_em_2023"])]
    out["faixa_450"] = [faixa_450(t, c) for t, c in zip(out["tipo_bem"], out["ce_100_em_2023"])]
    out["art454"] = [enquadrado_art454(a, z, t, k, pc) for a, z, t, k in
                     zip(out["aliq_tipi_2023"], out["produzido_zfm_2024"], out["eh_tic"], cas)]
    out["p_cbs_450"] = [p_cbs_450(a, z, t, pc, k) for a, z, t, k in
                        zip(out["aliq_tipi_2023"], out["produzido_zfm_2024"], out["eh_tic"], cas)]
    out["alerta_ibs"] = out["nivel_credito_estimulo"].astype(float) > 100 * out["p_ibs_450"]
    return out


# ---------------------------------------------------------------------------
# Insumos mensais por unidade de apuracao
# ---------------------------------------------------------------------------
MEDIDAS = ["deb_cbs_base", "deb_ibs_base", "deb_ibs_ent446", "deb_ibs_saidas", "cred_cbs", "cred_ibs",
           "cp450_cbs", "base_incent_p_ibs", "deb_b55", "deb_b75", "deb_b90_25", "deb_b100", "cp447_cheio", "cp449_cheio", "cp444_base", "receita_incent", "exportacao",
           "transferencias", "base_zfm_interna", "ipi_conc_as_is", "ipi_conc_prot", "icms_as_is", "ipi_as_is"]


def _sim(chave: str, padrao: str = "sim") -> bool:
    return params.premissa(None, chave, padrao).strip().lower() in ("sim", "s")


def unidade_apuracao() -> str:
    v = params.premissa(None, "nivel_apuracao_cbs_ibs", "raiz").strip().lower()
    return "cnpj_estab" if v.startswith("estab") else "raiz"


class _ProdutosRegistrados:
    """Registra no banco (temporariamente) os percentuais do art. 450 por produto."""

    def __init__(self, con: duckdb.DuckDBPyConnection):
        self.con = con

    def __enter__(self):
        prod = produtos_com_percentuais(params.carregar("param_produtos"))
        cols = ["raiz_cnpj", "cod_item", "p_cbs_450", "p_ibs_450", "eh_tic", "faixa_450"]
        df = prod[cols] if not prod.empty else pd.DataFrame(
            {"raiz_cnpj": pd.Series(dtype=str), "cod_item": pd.Series(dtype=str),
             "p_cbs_450": pd.Series(dtype=float), "p_ibs_450": pd.Series(dtype=float),
             "eh_tic": pd.Series(dtype=bool), "faixa_450": pd.Series(dtype=str)})
        self.con.register("_prod_pct", df)
        return self

    def __exit__(self, *exc):
        self.con.unregister("_prod_pct")


def conservador_padrao() -> bool:
    return params.premissa(None, "tratamento_nao_confirmados", "estimativa_com_incentivo").strip() == "regra_geral"


def sql_base_cenarios(f: Filtro, conservador: bool | None = None) -> str:
    """Operacoes classificadas + regra To Be do cenario + percentuais (uma linha por operacao).
    Nao elegivel ja chega como GER_S/GER_E (v_cenarios). conservador=True: operacoes potencialmente
    elegiveis ou com informacao insuficiente tambem vao para a regra geral (cenario de perda de requisito).
    Requer _ProdutosRegistrados ativo."""
    if conservador is None:
        conservador = conservador_padrao()
    pc = percentuais()
    liquida = params.premissa(None, "base_cbs_ibs", "liquida_sem_tributos") == "liquida_sem_tributos"
    transf = _sim("transferencias_na_base_cbs_ibs", "nao")
    tipi_regra = params.premissa(None, "ipi_protegido_regra", "tipi").strip().lower()
    prot = (f"c.aliq_tipi >= {pc['limite_tipi_ipi']}" if tipi_regra == "tipi"
            else f"c.ipi_protegido AND c.aliq_tipi >= {pc['limite_tipi_ipi']}")
    return f"""
        SELECT c.*,
               c.valor - CASE WHEN {liquida} THEN c.icms + c.pis + c.cofins ELSE 0 END AS base,
               CASE coalesce(r.entrada_creditavel, 'regime') WHEN 'sim' THEN 1.0 WHEN 'nao' THEN 0.0
                    ELSE CASE WHEN c.regime_estab = 'regular' THEN 1.0 ELSE 0.0 END END AS credok,
               CASE WHEN c.regime_estab = 'regular' THEN 1.0 ELSE 0.0 END AS regular,
               coalesce(r.cbs_debito, 0) AS r_cbs_debito, coalesce(r.ibs_debito, 0) AS r_ibs_debito,
               coalesce(r.cbs_entrada, 0) AS r_cbs_entrada, coalesce(r.ibs_entrada, 0) AS r_ibs_entrada,
               coalesce(r.cbs_credito_fornecedor, 0) AS r_cbs_forn, coalesce(r.ibs_credito_fornecedor, 0) AS r_ibs_forn,
               coalesce(r.cp_cbs_450, FALSE) AND c.incentivado AS r_cp_cbs,
               coalesce(r.cp_ibs_450, FALSE) AND c.incentivado AS r_cp_ibs,
               coalesce(r.cp_ibs_entrada, '') AS r_cp_ent,
               coalesce(pp.p_cbs_450, 0) AS p_cbs, coalesce(pp.p_ibs_450, 0) AS p_ibs,
               coalesce(pp.faixa_450, '55') AS faixa,
               CASE WHEN c.sul_sudeste_exceto_es THEN {pc['cp447_sul_sudeste_exceto_es'] / 100}
                    ELSE {pc['cp447_demais_e_es'] / 100} END AS pct447,
               {pc['cp449'] / 100} AS pct449,
               coalesce({prot}, FALSE) AS ipi_prot
        FROM v_cenarios c
        LEFT JOIN _prod_pct pp ON pp.raiz_cnpj = c.raiz AND pp.cod_item = c.cod_item
        LEFT JOIN param_regras_cenario r ON r.cenario = CASE
             WHEN c.cenario = 'TR' AND {transf} THEN CASE c.sentido WHEN 'saida' THEN 'GER_S' ELSE 'GER_E' END
             WHEN {conservador} AND c.cenario SIMILAR TO 'C[0-9].*'
                  AND c.status_elegibilidade <> 'Elegível' THEN CASE c.sentido WHEN 'saida' THEN 'GER_S' ELSE 'GER_E' END
             ELSE c.cenario END
        WHERE {f.sql('c.raiz', 'c.cnpj_estab', 'c.mes')}"""


AGREGADOS = """
    sum(x.base * x.r_cbs_debito) + sum(x.base * x.r_cbs_entrada * (1 - x.credok)) AS deb_cbs_base,
    sum(x.base * x.r_ibs_debito)
        + coalesce(sum(x.base * x.r_ibs_entrada * (1 - x.credok)) FILTER (WHERE x.cenario NOT LIKE 'C2%'), 0)
        AS deb_ibs_base,
    sum(x.base * x.r_ibs_entrada * (1 - x.credok)) FILTER (WHERE x.cenario LIKE 'C2%') AS deb_ibs_ent446,
    sum(x.base * x.r_ibs_debito) AS deb_ibs_saidas,
    sum(x.base * x.r_ibs_debito) FILTER (WHERE x.r_cp_ibs AND x.faixa = '55') AS deb_b55,
    sum(x.base * x.r_ibs_debito) FILTER (WHERE x.r_cp_ibs AND x.faixa = '75') AS deb_b75,
    sum(x.base * x.r_ibs_debito) FILTER (WHERE x.r_cp_ibs AND x.faixa = '90_25') AS deb_b90_25,
    sum(x.base * x.r_ibs_debito) FILTER (WHERE x.r_cp_ibs AND x.faixa = '100') AS deb_b100,
    sum(x.base * x.r_cbs_forn * x.regular) AS cred_cbs,
    sum(x.base * x.r_ibs_forn * x.regular) AS cred_ibs,
    sum(x.base * x.p_cbs * x.r_cbs_debito) FILTER (WHERE x.r_cp_cbs) AS cp450_cbs,
    sum(x.base * x.p_ibs * x.r_ibs_debito) FILTER (WHERE x.r_cp_ibs) AS base_incent_p_ibs,
    sum(x.base * x.pct447 * x.regular) FILTER (WHERE x.r_cp_ent = '447') AS cp447_cheio,
    sum(x.base * x.pct449 * x.regular) FILTER (WHERE x.r_cp_ent = '449') AS cp449_cheio,
    sum(x.base) FILTER (WHERE x.r_cp_ent = '444') AS cp444_base,
    sum(x.valor) FILTER (WHERE x.cenario LIKE 'C4%') AS receita_incent,
    sum(x.valor) FILTER (WHERE x.cenario = 'EXP') AS exportacao,
    sum(x.valor) FILTER (WHERE x.cenario = 'TR' AND x.sentido = 'saida') AS transferencias,
    sum(x.base) FILTER (WHERE x.cenario IN ('C4c', 'C4d')) AS base_zfm_interna,
    sum(x.valor * x.aliq_tipi / 100) FILTER (WHERE x.cenario LIKE 'C4%' AND x.aliq_tipi IS NOT NULL)
        AS ipi_conc_as_is,
    sum(x.valor * x.aliq_tipi / 100) FILTER (WHERE x.cenario LIKE 'C4%' AND x.ipi_prot) AS ipi_conc_prot
"""


def insumos_mensais(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS, conservador: bool | None = None) -> pd.DataFrame:
    """Uma linha por (unidade, raiz, mes) com as medidas que o motor usa, a partir das
    operacoes classificadas nos cenarios e das regras de param_regras_cenario."""
    unid = unidade_apuracao()
    with _ProdutosRegistrados(con):
        ops = con.execute(f"""
            WITH x AS ({sql_base_cenarios(f, conservador)})
            SELECT x.{unid} AS unidade, x.raiz, x.mes, {AGREGADOS}
            FROM x GROUP BY 1, 2, 3""").df()
    ap = _as_is.carga_mensal(con, f)
    ap = ap[ap["tributo"].isin(["ICMS", "IPI"])]
    if not ap.empty:
        ap = ap.assign(unidade=ap[unid] if unid == "raiz" else ap["cnpj_estab"])
        ap = ap.pivot_table(index=["unidade", "raiz", "mes"], columns="tributo", values="carga",
                            aggfunc="sum", fill_value=0.0).reset_index()
        ap = ap.rename(columns={"ICMS": "icms_as_is", "IPI": "ipi_as_is"})
    partes = [d for d in (ops, ap) if not d.empty]
    out = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=["unidade", "raiz", "mes"])
    for c in MEDIDAS:
        if c not in out.columns:
            out[c] = 0.0
    out[MEDIDAS] = out[MEDIDAS].astype(float).fillna(0.0)
    return out.groupby(["unidade", "raiz", "mes"], as_index=False)[MEDIDAS].sum()


def perfil_anual(mensal: pd.DataFrame, colunas: list[str], chaves: list[str],
                 meses_obs: dict | None = None, constante: bool = False) -> pd.DataFrame:
    """12 meses por chave: mes observado = valor do mes; mes sem dado = media dos observados
    (ou media em todos os meses, se constante). Soma anual = media mensal × 12.
    meses_obs: {raiz: [meses]} — meses observados da empresa (inclusive meses sem operacao)."""
    linhas = []
    for k, g in mensal.groupby(chaves):
        k = k if isinstance(k, tuple) else (k,)
        chave = dict(zip(chaves, k))
        obs = sorted(meses_obs.get(chave.get("raiz"), [])) if meses_obs else sorted(g["mes"].unique())
        g = g.set_index("mes")[colunas]
        g = g.reindex(sorted(set(obs) | set(g.index))).fillna(0.0)
        if obs:
            g = g.loc[[m for m in g.index if m in obs]]
        media = g.mean() if len(g) else pd.Series(0.0, index=colunas)
        for mes in range(1, 13):
            v = media if constante or mes not in g.index else g.loc[mes]
            linhas.append(dict(chave, mes=mes, observado=mes in g.index, **v.to_dict()))
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


def _num(v, padrao: float = 0.0) -> float:
    return float(v) if v is not None and pd.notna(v) else padrao


_ACUMULA = ("debito_cbs", "credito_cbs", "cp_cbs_gerado", "cp_cbs_usado", "cp_cbs_expirado", "cbs_pagar",
            "debito_ibs", "credito_ibs", "cp_entrada_gerado", "cp_entrada_usado", "cp_entrada_expirado",
            "cp_ibs_450", "ibs_pagar", "icms_to_be", "ipi_to_be", "contrib_457", "teses_icms", "teses_ipi",
            "ipi_conc_as_is", "ipi_conc_to_be", "base_zfm_interna", "exportacao", "transferencias",
            "receita_incent") + tuple(f"sd_{k}" for k in ("55", "75", "90_25", "100")) \
    + tuple(f"cp450_{k}" for k in ("55", "75", "90_25", "100"))


def simular(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS,
            com_teses: bool = False, conservador: bool | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (anual, mensal).

    anual: cenario × ano × raiz com carga To Be, carga As Is, diferenca por tributo,
           componentes (saidas × entradas), absorcao e vantagem competitiva do IPI.
    mensal: teste de absorcao mes a mes (cenario × ano × mes × raiz)."""
    from . import regras
    ins = insumos_mensais(con, f, conservador)
    if ins.empty:
        return pd.DataFrame(), pd.DataFrame()
    meses_df = _as_is.meses_observados(con, f)
    meses_obs = {r: sorted(g["mes"]) for r, g in meses_df.groupby("raiz")}
    constante = params.premissa(None, "anualizacao_mensal", "perfil_observado").strip() == "media_constante"
    perfil = perfil_anual(ins, MEDIDAS, ["unidade", "raiz"], meses_obs, constante)
    cen = _cenarios()
    prazo = int(params.premissa_num("prazo_cp_anos", 5) * 12)
    ordem_450_antes = params.premissa(None, "ordem_deducao_ibs", "").strip().endswith("cp450-cp447_449")
    tab_regras = regras.carregar()
    pc = percentuais()
    p_faixa = {k: (regras.pct(c, tab_regras) or 0.0) / 100 for k, c in FAIXAS_450.items()}
    fator_ipi = params.premissa_num("fator_ipi_proprio", 0.0)
    teses = _as_is.teses_mensais(con, f, False) if com_teses else pd.DataFrame()
    tes_mes = teses.groupby(["raiz", "mes", "tributo"])["valor"].sum().to_dict() if not teses.empty else {}
    teses_t = params.carregar("param_teses") if com_teses else pd.DataFrame()
    n_unid = perfil.groupby("raiz")["unidade"].nunique().to_dict()

    anual_u, mensal_u = [], []
    for cenario, cg in cen.groupby("cenario", sort=False):
        cg = cg.set_index("ano")
        for (unidade, raiz), pr in perfil.groupby(["unidade", "raiz"]):
            pr = pr.set_index("mes")
            cp_cbs, cp_ibs = Safras(prazo), Safras(prazo)
            normal_cbs = normal_ibs = 0.0
            idx = 0
            for ano in ANOS:
                if ano not in cg.index:
                    continue
                r = cg.loc[ano]
                a_cbs, a_ibs = _num(r["aliq_cbs"]) / 100, _num(r["aliq_ibs"]) / 100
                fator = _num(r["fator_icms"])
                f_cp = _num(r["fator_cp_entrada"])
                aplica450 = bool(r["aplica_cp_450"])
                sem_ipi = str(r["ipi_protegido_override"]).strip().lower() in ("nao", "não", "false")
                a457 = _num(r["aliq_contrib_art457"]) / 100
                # vigencia das regras (param_regras_legais): fora da vigencia o componente nao se aplica
                v444 = regras.fator("ART444_CP_IBS", ano, tab_regras)
                v446 = regras.fator("ART446_IBS_ENTRADA", ano, tab_regras)
                v447 = regras.fator("ART447_SS", ano, tab_regras)
                v449 = regras.fator("ART449_CP_IBS", ano, tab_regras)
                v450i = regras.fator("ART450_IBS_FINAL", ano, tab_regras)
                v450c = regras.fator("ART450_CBS_DEMAIS", ano, tab_regras)
                p446 = pc["ibs_entrada_446"] / 100 if pc["ibs_entrada_446"] else 0.0
                p444 = pc["cp444"] / 100 if pc["cp444"] else 0.0
                acc = {k: 0.0 for k in _ACUMULA}
                acc["meses_saldo_credor"] = 0.0
                for mes in range(1, 13):
                    v = pr.loc[mes]
                    # ---------------- CBS
                    deb = v["deb_cbs_base"] * a_cbs
                    cred = v["cred_cbs"] * a_cbs
                    cp_new = v["cp450_cbs"] if (aplica450 and v450c) else 0.0
                    exp_c = cp_cbs.expirar(idx)
                    liq = deb - cred - normal_cbs
                    normal_cbs = max(0.0, -liq)
                    liq = max(0.0, liq)
                    cp_cbs.adicionar(idx, cp_new)
                    usado_c = cp_cbs.usar(liq)
                    cbs_pagar = liq - usado_c
                    # ---------------- IBS
                    # IBS na entrada (art. 446): base × aliquota × percentual legal, a partir da vigencia
                    deb_i = v["deb_ibs_base"] * a_ibs + v["deb_ibs_ent446"] * a_ibs * p446 * v446
                    cred_i = v["cred_ibs"] * a_ibs
                    cp_ent = ((v["cp447_cheio"] * v447 + v["cp449_cheio"] * v449) * f_cp
                              + v["cp444_base"] * a_ibs * p444 * v444 if a_ibs > 0 else 0.0)
                    exp_i = cp_ibs.expirar(idx)
                    liq_i = deb_i - cred_i - normal_ibs
                    normal_ibs = max(0.0, -liq_i)
                    liq_i = max(0.0, liq_i)
                    cp_ibs.adicionar(idx, cp_ent)
                    aplica450_ibs = aplica450 and bool(v450i)

                    def faixas_450(saldo: float) -> dict:
                        """Art. 450 de IBS por faixa: saldo devedor de cada faixa = saldo do periodo × debitos da
                        faixa ÷ debitos de IBS das saidas (criterio 'proporcional_debito' de alocacao dos creditos);
                        credito presumido = saldo da faixa × percentual da faixa. A parcela nao elegivel fica sem CP."""
                        tot = v["deb_ibs_saidas"]
                        out = {}
                        for k in FAIXAS_450:
                            sd = saldo * v[f"deb_b{k}"] / tot if (tot > 0 and aplica450_ibs) else 0.0
                            out[f"sd_{k}"] = max(0.0, sd)
                            out[f"cp450_{k}"] = max(0.0, sd) * p_faixa[k]
                        return out

                    if ordem_450_antes:
                        fx = faixas_450(liq_i)
                        cp450_ibs = sum(fx[f"cp450_{k}"] for k in FAIXAS_450)
                        usado_i = cp_ibs.usar(liq_i - cp450_ibs)
                        ibs_pagar = liq_i - cp450_ibs - usado_i
                    else:
                        usado_i = cp_ibs.usar(liq_i)
                        saldo_dev = liq_i - usado_i
                        fx = faixas_450(saldo_dev)
                        cp450_ibs = sum(fx[f"cp450_{k}"] for k in FAIXAS_450)
                        ibs_pagar = saldo_dev - cp450_ibs
                    # ---------------- ICMS residual, IPI proprio, art. 457, teses
                    icms = v["icms_as_is"] * fator
                    ipi = v["ipi_as_is"] * fator_ipi
                    c457 = v["receita_incent"] * a457
                    t_icms = t_ipi = 0.0
                    if com_teses and n_unid.get(raiz, 1) and not teses_t.empty:
                        parte = 1.0 / n_unid.get(raiz, 1)
                        t_icms, t_ipi = _teses_to_be(teses_t, raiz, ano, mes, v["receita_incent"], fator,
                                                     fator_ipi)
                        t_icms, t_ipi = t_icms * parte, t_ipi * parte
                    saldo_credor = (cp_cbs.saldo + cp_ibs.saldo + normal_cbs + normal_ibs) > 0.005
                    valores = {"debito_cbs": deb, "credito_cbs": cred, "cp_cbs_gerado": cp_new,
                               "cp_cbs_usado": usado_c, "cp_cbs_expirado": exp_c, "cbs_pagar": cbs_pagar,
                               "debito_ibs": deb_i, "credito_ibs": cred_i, "cp_entrada_gerado": cp_ent,
                               "cp_entrada_usado": usado_i, "cp_entrada_expirado": exp_i,
                               "cp_ibs_450": cp450_ibs, "ibs_pagar": ibs_pagar, "icms_to_be": icms,
                               "ipi_to_be": ipi, "contrib_457": c457, "teses_icms": t_icms,
                               "teses_ipi": t_ipi, "ipi_conc_as_is": v["ipi_conc_as_is"],
                               "ipi_conc_to_be": 0.0 if sem_ipi else v["ipi_conc_prot"],
                               "base_zfm_interna": v["base_zfm_interna"], "exportacao": v["exportacao"],
                               "transferencias": v["transferencias"], "receita_incent": v["receita_incent"], **fx}
                    for k2, val in valores.items():
                        acc[k2] += val
                    acc["meses_saldo_credor"] += 1.0 if saldo_credor else 0.0
                    mensal_u.append({"cenario": cenario, "ano": ano, "mes": mes, "raiz": raiz,
                                     "unidade": unidade, "observado": bool(v["observado"]),
                                     "cbs_pagar": cbs_pagar, "ibs_pagar": ibs_pagar,
                                     "cp_cbs_gerado": cp_new, "cp_cbs_usado": usado_c,
                                     "cp_cbs_expirado": exp_c, "saldo_cp_cbs": cp_cbs.saldo,
                                     "cp_entrada_gerado": cp_ent, "cp_entrada_usado": usado_i,
                                     "cp_entrada_expirado": exp_i, "saldo_cp_ibs": cp_ibs.saldo,
                                     "saldo_credor_normal_cbs": normal_cbs,
                                     "saldo_credor_normal_ibs": normal_ibs, **fx,
                                     "saldo_credor": bool(saldo_credor)})
                    idx += 1
                anual_u.append({"cenario": cenario, "ano": ano, "raiz": raiz, "unidade": unidade, **acc})
    anual = pd.DataFrame(anual_u)
    mensal = pd.DataFrame(mensal_u)
    soma = [c for c in anual.columns if c not in ("cenario", "ano", "raiz", "unidade", "meses_saldo_credor")]
    anual = anual.groupby(["cenario", "ano", "raiz"], as_index=False, sort=False).agg(
        {**{c: "sum" for c in soma}, "meses_saldo_credor": "max"})
    if not mensal.empty:
        num = [c for c in mensal.columns if c not in ("cenario", "ano", "mes", "raiz", "unidade",
                                                      "observado", "saldo_credor")]
        mensal = mensal.groupby(["cenario", "ano", "mes", "raiz"], as_index=False, sort=False).agg(
            {**{c: "sum" for c in num}, "observado": "max", "saldo_credor": "max"})
    return _completar(anual, _as_is.carga_anual(con, f, com_teses)), mensal


def _teses_to_be(teses: pd.DataFrame, raiz: str, ano: int, mes: int, receita: float,
                 fator_icms: float, fator_ipi: float) -> tuple[float, float]:
    """Teses no To Be (reducao de carga). Tributo extinto perde efeito prospectivo:
    PIS/COFINS deixam de existir em 2027; ICMS segue o fator do ano; IPI o fator do IPI proprio."""
    from . import beneficio_atual as ba
    ja = params.premissa(None, "teses_ativas_ja_na_apuracao", "sim").strip().lower() in ("sim", "s")
    geral = ba._aliq_geral()
    icms = ipi = 0.0
    for t in teses.itertuples():
        if t.raiz_cnpj not in ("", "todas", raiz) or not ba.em_vigencia(t, ano, mes):
            continue
        if ja and str(t.status).strip().lower() == "ativa":
            continue  # ja embutida no ICMS/IPI As Is × fator
        trib = t.tributo.upper()
        v = ba.valor_tese(t, receita, geral)
        if trib == "ICMS":
            icms += v * fator_icms
        elif trib == "IPI":
            ipi += v * fator_ipi
    return icms, ipi


TRIB_TO_BE = ["ICMS", "IPI", "PIS", "COFINS", "CBS", "IBS", "CONTRIB_457"]


def _completar(anual: pd.DataFrame, asis: pd.DataFrame) -> pd.DataFrame:
    """Junta As Is (apuracao) e calcula carga To Be, diferencas, ponte e vantagem do IPI."""
    a = anual.copy()
    piv = {}
    nomes = {"as_is": "as_is", "as_is_base": "as_is_base", "ajuste_reconciliacao": "ajuste_reconciliacao",
             "teses": "teses_as_is"}
    for col, pref in nomes.items():
        if asis.empty:
            continue
        p = asis.pivot_table(index="raiz", columns="tributo", values=col, aggfunc="sum", fill_value=0.0)
        for t in ("ICMS", "IPI", "PIS", "COFINS"):
            piv[f"{pref}_{t.lower()}"] = p[t] if t in p.columns else pd.Series(dtype=float)
    for k, serie in piv.items():
        a[k] = a["raiz"].map(serie).fillna(0.0)
    for t in ("icms", "ipi", "pis", "cofins"):
        for pref in nomes.values():
            if f"{pref}_{t}" not in a.columns:
                a[f"{pref}_{t}"] = 0.0
    # carga To Be por tributo (teses ja descontadas)
    a["to_be_icms"] = a["icms_to_be"] - a["teses_icms"]
    a["to_be_ipi"] = a["ipi_to_be"] - a["teses_ipi"]
    a["to_be_pis"] = 0.0
    a["to_be_cofins"] = 0.0
    a["to_be_cbs"] = a["cbs_pagar"]
    a["to_be_ibs"] = a["ibs_pagar"]
    a["to_be_contrib_457"] = a["contrib_457"]
    a["as_is_cbs"] = a["as_is_ibs"] = a["as_is_contrib_457"] = 0.0
    for t in TRIB_TO_BE:
        k = t.lower()
        a[f"dif_{k}"] = a[f"to_be_{k}"] - a[f"as_is_{k}"]
    a["to_be_total"] = sum(a[f"to_be_{t.lower()}"] for t in TRIB_TO_BE)
    a["as_is_total"] = sum(a[f"as_is_{t}"] for t in ("icms", "ipi", "pis", "cofins"))
    a["as_is_base_total"] = sum(a[f"as_is_base_{t}"] for t in ("icms", "ipi", "pis", "cofins"))
    a["ajuste_reconciliacao_total"] = a["as_is_total"] - a["as_is_base_total"]
    a["diferenca_total"] = a["to_be_total"] - a["as_is_total"]
    # teorico: credito presumido todo aproveitado (sem limite do debito e sem vencimento)
    a["to_be_cbs_teorico"] = a["debito_cbs"] - a["credito_cbs"] - a["cp_cbs_gerado"]
    a["to_be_ibs_teorico"] = a["debito_ibs"] - a["credito_ibs"] - a["cp_entrada_gerado"] - a["cp_ibs_450"]
    a["to_be_total_teorico"] = (a["to_be_total"] - a["to_be_cbs"] - a["to_be_ibs"]
                                + a["to_be_cbs_teorico"] + a["to_be_ibs_teorico"])
    a["diferenca_total_teorica"] = a["to_be_total_teorico"] - a["as_is_total"]
    # vantagem competitiva (IPI do concorrente de fora): positivo = perda de vantagem
    a["perda_vantagem_ipi"] = a["ipi_conc_as_is"] - a["ipi_conc_to_be"]
    return a


def ponte(anual: pd.DataFrame, cenario: str, ano: int, raizes: list[str] | None = None) -> pd.DataFrame:
    """Waterfall da carga: As Is → efeitos por tributo → To Be (etapa 8)."""
    a = anual[(anual.cenario == cenario) & (anual.ano == ano)]
    if raizes is not None:
        a = a[a.raiz.isin(raizes)]
    s = a.sum(numeric_only=True)
    g = lambda k: float(s.get(k, 0.0))  # noqa: E731
    passos = [
        ("Carga As Is (apuração)", g("as_is_total"), "absolute"),
        ("Ajuste de reconciliação (base × apuração)", -g("ajuste_reconciliacao_total"), "relative"),
        ("Efeito CBS (substitui PIS/COFINS)", g("to_be_cbs") - g("as_is_base_pis") - g("as_is_base_cofins"), "relative"),
        ("Efeito IBS", g("to_be_ibs"), "relative"),
        ("Efeito ICMS residual", g("to_be_icms") - g("as_is_base_icms"), "relative"),
        ("Efeito IPI", g("to_be_ipi") - g("as_is_base_ipi"), "relative"),
        ("Contribuição art. 457", g("to_be_contrib_457"), "relative"),
        ("Carga To Be", g("to_be_total"), "total"),
    ]
    return pd.DataFrame(passos, columns=["etapa", "valor", "medida"])


def diferenca_por_tributo(anual: pd.DataFrame) -> pd.DataFrame:
    """Formato longo: cenario, ano, raiz, tributo, as_is, to_be, diferenca (positivo = perda)."""
    linhas = []
    for t in TRIB_TO_BE:
        k = t.lower()
        d = anual[["cenario", "ano", "raiz"]].copy()
        d["tributo"] = "Contribuição art. 457" if t == "CONTRIB_457" else t
        d["as_is"] = anual[f"as_is_{k}"]
        d["to_be"] = anual[f"to_be_{k}"]
        d["diferenca"] = anual[f"dif_{k}"]
        linhas.append(d)
    if not linhas:
        return pd.DataFrame()
    out = pd.concat(linhas, ignore_index=True)
    ordem = [("Contribuição art. 457" if t == "CONTRIB_457" else t) for t in TRIB_TO_BE]
    out["tributo"] = pd.Categorical(out["tributo"], categories=ordem, ordered=True)
    return out


LADOS = {"saidas": "Saídas", "entradas": "Entradas", "outros": "Deduções, fundos e saldos"}


def composicao(anual: pd.DataFrame, con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    """Carga decomposta em saidas (debitos e CP de saida), entradas (creditos e CP de entrada)
    e outros (deducoes, fundos, saldos), As Is × To Be. Formato longo."""
    meses = _as_is.meses_observados(con, f)
    m = _as_is.carga_mensal(con, f)
    comp_as = []
    if not m.empty:
        for col, lado, nome in (("saidas_debitos", "saidas", "Débitos sobre saídas"),
                                ("entradas_creditos", "entradas", "Créditos das entradas"),
                                ("deducoes_beneficios", "outros", "Deduções (inclui crédito estímulo)"),
                                ("fundos_fora_apuracao", "outros", "Fundos/obrigações fora da apuração"),
                                ("efeito_saldo", "outros", "Efeito de saldo credor")):
            x = _as_is.anualizar(m, meses, col).rename(columns={col: "valor"})
            x["lado"], x["componente"] = lado, nome
            comp_as.append(x)
    asis = pd.concat(comp_as, ignore_index=True) if comp_as else pd.DataFrame(
        columns=["raiz", "tributo", "valor", "lado", "componente"])
    linhas = []
    for (cen, ano), g in anual.groupby(["cenario", "ano"], sort=False):
        fat = _cenarios().set_index(["cenario", "ano"])
        fi = _num(fat.loc[(cen, ano), "fator_icms"]) if (cen, ano) in fat.index else 0.0
        fipi = params.premissa_num("fator_ipi_proprio", 0.0)
        for r in g.itertuples():
            base = {"cenario": cen, "ano": ano, "raiz": r.raiz}
            for t in ("ICMS", "IPI", "PIS", "COFINS"):
                v = float(getattr(r, f"teses_as_is_{t.lower()}", 0.0) or 0.0)
                if v:
                    linhas.append({**base, "regime": "As Is", "tributo": t, "lado": "outros",
                                   "componente": "Teses", "valor": -v})
            for _, x in asis[asis.raiz == r.raiz].iterrows():
                linhas.append({**base, "regime": "As Is", "tributo": x.tributo, "lado": x.lado,
                               "componente": x.componente, "valor": x.valor})
                fator = fi if x.tributo == "ICMS" else fipi if x.tributo == "IPI" else 0.0
                if x.tributo in ("ICMS", "IPI") and fator:
                    linhas.append({**base, "regime": "To Be", "tributo": x.tributo, "lado": x.lado,
                                   "componente": x.componente, "valor": x.valor * fator})
            for trib, itens in (
                ("CBS", (("saidas", "Débitos sobre saídas", r.debito_cbs),
                         ("saidas", "Crédito presumido de saída (art. 450)", -r.cp_cbs_usado),
                         ("entradas", "Créditos das entradas", -r.credito_cbs),
                         ("outros", "Efeito de saldo credor",
                          r.cbs_pagar - (r.debito_cbs - r.cp_cbs_usado - r.credito_cbs)))),
                ("IBS", (("saidas", "Débitos sobre saídas", r.debito_ibs),
                         ("saidas", "Crédito presumido de saída (art. 450)", -r.cp_ibs_450),
                         ("entradas", "Créditos das entradas", -r.credito_ibs),
                         ("entradas", "Crédito presumido de entrada (arts. 447/449)", -r.cp_entrada_usado),
                         ("outros", "Efeito de saldo credor",
                          r.ibs_pagar - (r.debito_ibs - r.cp_ibs_450 - r.credito_ibs - r.cp_entrada_usado)))),
                ("Contribuição art. 457", (("saidas", "Contribuição sobre a receita incentivada",
                                            r.contrib_457),)),
                ("ICMS", (("outros", "Teses", -r.teses_icms),)),
                ("IPI", (("outros", "Teses", -r.teses_ipi),))):
                for lado, nome, val in itens:
                    if abs(val) > 1e-9:
                        linhas.append({**base, "regime": "To Be", "tributo": trib, "lado": lado,
                                       "componente": nome, "valor": val})
    return pd.DataFrame(linhas)
