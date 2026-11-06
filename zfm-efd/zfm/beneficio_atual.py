"""Beneficio atual (As Is) - SPEC 7.5. Beneficio = carga no regime geral − carga efetiva na ZFM.

IPI    = saidas de producao incentivada (CST IPI isenta) × aliquota TIPI do produto
PIS    = receita incentivada × (1,65% − aliquota aplicada)
COFINS = receita incentivada × (7,6% − aliquota aplicada)
ICMS   = E111 credito estimulo − fundos (FTI/UEA/FMPES), alocado aos produtos pela
         receita incentivada do estabelecimento no mes
Saidas para exportacao ficam fora (imunes com ou sem ZFM).
Cada linha do resultado guarda arquivo_id/linha_num de origem (rastreabilidade).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from . import params

TRIBUTOS = ["IPI", "PIS", "COFINS", "ICMS"]
NAN = float("nan")


def _onde(cond: pd.Series, sim, nao) -> pd.Series:
    """Equivalente a numpy.where usando so pandas."""
    a = sim if isinstance(sim, pd.Series) else pd.Series(sim, index=cond.index)
    return a.where(cond, nao)


COLUNAS = ["raiz", "cnpj_estab", "mes", "cod_item", "tributo", "beneficio", "base",
           "aliq_regime_geral", "aliq_aplicada", "reg_origem", "arquivo_id", "linha_num",
           "rateado", "observacao"]


def saidas_incentivadas(con: duckdb.DuckDBPyConnection, eliminar_intragrupo: bool = False) -> pd.DataFrame:
    """Saidas de producao propria de produtos incentivados, estabelecimentos do AM,
    exceto exportacao; uma linha por item da EFD Contribuicoes (ja rateada por destino)."""
    df = con.execute("""
        SELECT s.raiz, s.cnpj_estab, s.mes, s.cod_item, s.cfop, s.tipo_operacao, s.eh_grupo,
               s.receita_r, CAST(s.aliq_pis AS DOUBLE) AS aliq_pis,
               CAST(s.aliq_cofins AS DOUBLE) AS aliq_cofins, s.pis_r, s.cofins_r, s.icms_est_r,
               s.cst_ipi, s.reg_origem, s.arquivo_id, s.linha_num, s.rateado,
               coalesce(p.aliq_tipi_2026, p.aliq_tipi_2023) AS aliq_tipi,
               p.tipo_bem, p.aliq_tipi_2023, p.produzido_zfm_2024, p.eh_tic, p.ipi_protegido,
               p.ce_100_em_2023, p.nivel_credito_estimulo
        FROM v_saidas_dest s
        JOIN param_produtos p ON p.raiz_cnpj = s.raiz AND p.cod_item = s.cod_item
        WHERE p.incentivado AND s.categoria_cfop = 'venda_producao' AND s.estab_no_am
          AND s.tipo_operacao <> 'exportacao'
    """).df()
    if eliminar_intragrupo and not df.empty:
        df = df[~df["eh_grupo"].fillna(False).astype(bool)]
    return df


def _aliq_geral() -> dict[str, float]:
    t = params.carregar("param_aliquotas_regime_geral")
    d = {r.tributo.upper(): float(r.aliquota) for r in t.itertuples() if pd.notna(r.aliquota)}
    return {"PIS": d.get("PIS", 1.65), "COFINS": d.get("COFINS", 7.6)}


def calcular(con: duckdb.DuckDBPyConnection, com_teses: bool = False,
             eliminar_intragrupo: bool = False) -> pd.DataFrame:
    s = saidas_incentivadas(con, eliminar_intragrupo)
    geral = _aliq_geral()
    partes: list[pd.DataFrame] = []
    if not s.empty:
        base = s[["raiz", "cnpj_estab", "mes", "cod_item", "reg_origem", "arquivo_id",
                  "linha_num", "rateado"]].copy()
        # ---- IPI
        isentos = {c.strip() for c in params.premissa(None, "cst_ipi_isento", "52").split(";") if c.strip()}
        assume = params.premissa(None, "ipi_sem_cst_assume_isento", "sim").strip().lower() in ("sim", "s")
        cst = s["cst_ipi"].fillna("")
        cst_ok = cst.isin(isentos) | ((cst == "") & assume)
        tipi = s["aliq_tipi"].astype(float)
        ipi = base.assign(tributo="IPI", base=s["receita_r"], aliq_regime_geral=tipi, aliq_aplicada=0.0,
                          beneficio=_onde(cst_ok & tipi.notna(), s["receita_r"] * tipi.fillna(0) / 100, 0.0))
        obs = pd.Series("", index=s.index)
        obs = obs.mask(cst == "", "CST de IPI não informado por item: premissa de isenção")
        obs = obs.mask(~cst_ok, "CST de IPI não é de isenção: fora do benefício")
        obs = obs.mask(tipi.isna(), "Alíquota TIPI não preenchida em Parâmetros > Produtos")
        ipi["observacao"] = obs
        partes.append(ipi)
        # ---- PIS / COFINS
        for trib, col in (("PIS", "aliq_pis"), ("COFINS", "aliq_cofins")):
            a = s[col]
            dif = (geral[trib] - a.fillna(geral[trib])).clip(lower=0)
            partes.append(base.assign(
                tributo=trib, base=s["receita_r"], aliq_regime_geral=geral[trib], aliq_aplicada=a,
                beneficio=s["receita_r"] * dif / 100,
                observacao=_onde(a.isna(), f"Sem registro de {trib} para o item", "")))
    # ---- ICMS (apuracao, alocado por receita incentivada)
    ap = con.execute("""
        SELECT a.raiz, a.cnpj_estab, a.mes, a.credito_estimulo, a.fundos, a.arquivo_id, a.linha_num
        FROM v_apur_icms a
        JOIN v_estabelecimentos e ON e.cnpj = a.cnpj_estab AND e.no_amazonas
        WHERE a.credito_estimulo <> 0 OR a.fundos <> 0""").df()
    if not ap.empty:
        ap["valor"] = ap["credito_estimulo"].astype(float) - ap["fundos"].astype(float)
        if not s.empty:
            pesos = s.groupby(["cnpj_estab", "mes", "cod_item"], as_index=False)["receita_r"].sum()
            pesos["peso"] = pesos["receita_r"] / pesos.groupby(["cnpj_estab", "mes"])["receita_r"].transform("sum")
        else:
            pesos = pd.DataFrame(columns=["cnpj_estab", "mes", "cod_item", "receita_r", "peso"])
        m = ap.merge(pesos, on=["cnpj_estab", "mes"], how="left")
        sem = m["peso"].isna()
        m.loc[sem, "peso"] = 1.0
        icms = pd.DataFrame({
            "raiz": m["raiz"], "cnpj_estab": m["cnpj_estab"], "mes": m["mes"],
            "cod_item": m["cod_item"].where(~sem, None), "tributo": "ICMS",
            "beneficio": m["valor"] * m["peso"], "base": m["receita_r"],
            "aliq_regime_geral": NAN, "aliq_aplicada": NAN, "reg_origem": "E110/E111/E116",
            "arquivo_id": m["arquivo_id"], "linha_num": m["linha_num"],
            "rateado": ~sem,
            "observacao": _onde(sem, "Sem receita incentivada no mês: não alocado a produto",
                                "Crédito estímulo − fundos, alocado pela receita incentivada")})
        partes.append(icms)
    if com_teses:
        partes.append(_teses_atual(con, s))
    partes = [p for p in partes if not p.empty]
    if not partes:
        return pd.DataFrame(columns=COLUNAS)
    out = pd.concat(partes, ignore_index=True)
    for c in COLUNAS:
        if c not in out.columns:
            out[c] = None
    return out[COLUNAS]


def _teses_atual(con: duckdb.DuckDBPyConnection, s: pd.DataFrame) -> pd.DataFrame:
    t = params.carregar("param_teses")
    if t.empty:
        return pd.DataFrame(columns=COLUNAS)
    ano = int(params.premissa_num("ano_base", 2026))
    meses = con.execute("SELECT DISTINCT raiz, month(dt_ini) AS mes FROM arquivos "
                        "WHERE ativo AND year(dt_ini) = ?", [ano]).df()
    geral = _aliq_geral()
    linhas = []
    for tese in t.itertuples():
        alvo = meses if tese.raiz_cnpj in ("", "todas") else meses[meses.raiz == tese.raiz_cnpj]
        for r in alvo.itertuples():
            if not em_vigencia(tese, ano, r.mes):
                continue
            rec = s[(s.raiz == r.raiz) & (s.mes == r.mes)]["receita_r"].sum() if not s.empty else 0
            v = valor_tese(tese, rec, geral)
            if v:
                linhas.append({"raiz": r.raiz, "cnpj_estab": None, "mes": r.mes,
                               "cod_item": f"TESE:{tese.tese_id}", "tributo": tese.tributo.upper(),
                               "beneficio": v, "base": rec, "reg_origem": "param_teses",
                               "rateado": False, "observacao": tese.descricao})
    return pd.DataFrame(linhas, columns=COLUNAS)


def em_vigencia(tese, ano: int, mes: int) -> bool:
    ym = f"{ano:04d}-{mes:02d}"
    ini = (tese.vigencia_ini or "").strip()
    fim = (tese.vigencia_fim or "").strip()
    return (not ini or ym >= ini[:7]) and (not fim or ym <= fim[:7])


def valor_tese(tese, receita_incentivada: float, geral: dict[str, float]) -> float:
    p = float(tese.parametro) if pd.notna(tese.parametro) else 0.0
    tipo = (tese.tipo_efeito or "").strip()
    if tipo in ("valor_fixo_mensal", "credito_adicional"):
        return p
    if tipo == "reduz_aliquota":
        return receita_incentivada * p / 100
    if tipo == "reduz_base":
        return receita_incentivada * p / 100 * geral.get(tese.tributo.upper(), 0.0) / 100
    return 0.0


# ---------------------------------------------------------------------------
# Resumos
# ---------------------------------------------------------------------------
def resumo_por_empresa(det: pd.DataFrame, receita: pd.DataFrame | None = None) -> pd.DataFrame:
    if det.empty:
        return pd.DataFrame()
    p = det.pivot_table(index="raiz", columns="tributo", values="beneficio", aggfunc="sum",
                        fill_value=0.0)
    for t in TRIBUTOS:
        if t not in p.columns:
            p[t] = 0.0
    p["Total"] = p.sum(axis=1)
    if receita is not None and not receita.empty:
        p = p.join(receita.set_index("raiz")["receita_incentivada"])
        p["% da receita incentivada"] = 100 * p["Total"] / p["receita_incentivada"].replace(0, NAN)
    return p.reset_index()


def receita_incentivada(con: duckdb.DuckDBPyConnection, eliminar_intragrupo: bool = False) -> pd.DataFrame:
    s = saidas_incentivadas(con, eliminar_intragrupo)
    if s.empty:
        return pd.DataFrame(columns=["raiz", "receita_incentivada"])
    return s.groupby("raiz", as_index=False)["receita_r"].sum().rename(
        columns={"receita_r": "receita_incentivada"})


def meses_observados(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    ano = int(params.premissa_num("ano_base", 2026))
    return con.execute("""SELECT raiz, count(DISTINCT month(dt_ini)) AS meses FROM arquivos
                          WHERE ativo AND tipo = 'ICMS_IPI' AND year(dt_ini) = ? GROUP BY 1""",
                       [ano]).df()


# ---------------------------------------------------------------------------
# Visao "so entradas" (informativa; nao entra no total - SPEC 7.5)
# ---------------------------------------------------------------------------
_CST_DESONERADO = {
    "ICMS": ("30", "40", "41", "50", "51"),          # 2 ultimos digitos do CST
    "IPI": ("02", "03", "04", "05"),                 # isenta, nao tributada, imune, suspensao
    "PIS": ("70", "71", "72", "73", "74", "75"),     # aquisicoes sem credito/isencao/suspensao/aliq. zero
    "COFINS": ("70", "71", "72", "73", "74", "75"),
}
_DESCR_CST = {"30": "isenta/não tributada c/ ST", "40": "isenta", "41": "não tributada",
              "50": "suspensão", "51": "diferimento", "02": "isenta", "03": "não tributada",
              "04": "imune", "05": "suspensão", "70": "sem direito a crédito",
              "71": "isenção", "72": "suspensão", "73": "alíquota zero", "74": "sem incidência",
              "75": "substituição tributária"}


def entradas_desoneradas(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Compras com isencao, suspensao ou aliquota zero, por tributo e CST (informativo).
    Para PIS/COFINS estima o tributo nao cobrado pela aliquota do regime geral."""
    e = con.execute("""SELECT raiz, cnpj_estab, mes, origem, regiao_origem, categoria_cfop, cst_icms,
                              cst_ipi, cst_pis, cst_cofins, CAST(valor AS DOUBLE) AS valor,
                              reg_origem, arquivo_id, linha_num
                       FROM v_entradas_item""").df()
    if e.empty:
        return pd.DataFrame(columns=["raiz", "mes", "tributo", "cst", "situacao", "origem",
                                     "valor_entradas", "tributo_nao_cobrado_estimado"])
    geral = _aliq_geral()
    partes = []
    for trib, col in (("ICMS", "cst_icms"), ("IPI", "cst_ipi"), ("PIS", "cst_pis"), ("COFINS", "cst_cofins")):
        cst = e[col].fillna("").astype(str)
        chave = cst.str[-2:] if trib == "ICMS" else cst
        m = chave.isin(_CST_DESONERADO[trib])
        d = e[m].assign(tributo=trib, cst=cst[m], situacao=chave[m].map(_DESCR_CST))
        d["valor_entradas"] = d["valor"]
        d["tributo_nao_cobrado_estimado"] = d["valor"] * geral.get(trib, NAN) / 100 \
            if trib in geral else NAN
        partes.append(d)
    out = pd.concat(partes, ignore_index=True)
    return out[["raiz", "cnpj_estab", "mes", "tributo", "cst", "situacao", "origem", "regiao_origem",
                "categoria_cfop", "valor_entradas", "tributo_nao_cobrado_estimado", "reg_origem",
                "arquivo_id", "linha_num"]]
