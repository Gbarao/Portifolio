"""Análise do Bloco M da EFD-Contribuições (apuração do PIS/Pasep e da Cofins) e do controle de créditos (1100/1500).

Fonte: as linhas originais guardadas na importação (tabela ec_linhas). Nada é recalculado nem cruzado com o SPED
Fiscal: os valores são os informados pelo contribuinte, registro a registro. Sobre eles a tela oferece:
  * demonstrativo da apuração por competência (M200/M600), créditos (M100/M500 + M105/M505), contribuição
    (M210/M610 + M205/M605), ajustes (M110/M510, M215/M615, M220/M620 e detalhamentos), receitas não tributadas
    (M400/M800 + M410/M810) e saldos de créditos de períodos anteriores (1100/1500);
  * verificações aritméticas entre os registros (ex.: M200 x soma dos M100);
  * conferência das bases de crédito do M105/M505 com os documentos da própria escrituração (blocos A, C, D e F).
"""
from __future__ import annotations

import re
from typing import Any

import polars as pl

from app import config
from app.database import tabelas_efd as T
from app.parser import catalog

TIPO = "CONTRIB"
PAIRS = {  # (PIS, COFINS)
    "credito": ("M100", "M500"), "base_credito": ("M105", "M505"), "aj_credito": ("M110", "M510"),
    "det_aj_credito": ("M115", "M515"), "consolidacao": ("M200", "M600"), "cod_receita": ("M205", "M605"),
    "contribuicao": ("M210", "M610"), "aj_base": ("M215", "M615"), "aj_contribuicao": ("M220", "M620"),
    "det_aj_contribuicao": ("M225", "M625"), "receita_nt": ("M400", "M800"), "receita_nt_det": ("M410", "M810"),
    "saldo": ("1100", "1500"),
}
REGS = sorted({r for p in PAIRS.values() for r in p})
TOL = 0.011


class BlocoMError(ValueError):
    pass


# --------------------------------------------------------------------------------------
# Leitura das linhas
# --------------------------------------------------------------------------------------
def _norm(name: str) -> str:
    n = re.sub(r"_(PIS|COFINS)(?=_|$)", "", name)
    n = {"VL_CRED_DIFER": "VL_CRED_DIF", "IND_AJ_BC": "IND_AJ", "VL_AJ_BC": "VL_AJ", "COD_AJ_BC": "COD_AJ",
         "DESCR_AJ_BC": "DESCR_AJ"}.get(n, n)
    return n.lower()


def file_ids(db, q: dict) -> list[int]:
    conds, params = ["ativo", "tipo_sped = ?"], [TIPO]
    if q.get("empresas"):
        conds.append("cnpj IN (SELECT unnest(?))")
        params.append([str(x) for x in q["empresas"]])
    if q.get("competencias"):
        conds.append("competencia IN (SELECT unnest(?))")
        params.append([str(c) for c in q["competencias"]])
    if q.get("comp_ini"):
        conds.append("competencia >= ?")
        params.append(str(q["comp_ini"]))
    if q.get("comp_fim"):
        conds.append("competencia <= ?")
        params.append(str(q["comp_fim"]))
    df = db.query(f"SELECT id_arquivo FROM sys_arquivos_importados WHERE {' AND '.join(conds)}", params)
    return [int(x) for x in df["id_arquivo"].to_list()] if df.height else []


def _raw(db, ids: list[int]) -> pl.DataFrame:
    if not ids:
        return pl.DataFrame()
    df = db.query(f"""
        SELECT l.file_id, l.line_no, l.doc_line, l.reg, l.linha, a.competencia, a.cnpj AS cnpj_empresa,
               a.nome AS nome_empresa
        FROM ec_linhas l JOIN sys_arquivos_importados a ON a.id_arquivo = l.file_id
        WHERE l.file_id IN ({','.join(map(str, ids))}) AND l.reg IN (SELECT unnest(?))""", [REGS])
    if df.height == 0:
        return df
    return df.with_columns(pl.col("linha").str.split("|").alias("f")).with_columns(
        (pl.col("f").list.len() - 3).alias("nf"))


def _cast(expr: pl.Expr, kind: str) -> pl.Expr:
    e = pl.when(expr == "").then(None).otherwise(expr)
    if kind in ("money", "qty"):
        return e.str.replace(",", ".", literal=True).cast(pl.Float64, strict=False)
    if kind == "date":
        return e.str.strptime(pl.Date, "%d%m%Y", strict=False)
    return e


def _reg(raw: pl.DataFrame, reg: str) -> pl.DataFrame:
    """Linhas de um registro com os campos do leiaute (nomes normalizados, sem _PIS/_COFINS)."""
    base_cols = ["file_id", "line_no", "doc_line", "competencia", "cnpj_empresa", "nome_empresa", "nf"]
    main = catalog.LAYOUTS[TIPO][reg]
    if raw.height == 0:
        kinds = {"money": pl.Float64, "qty": pl.Float64, "date": pl.Date}
        return pl.DataFrame(schema={
            "file_id": pl.Int64, "line_no": pl.Int64, "doc_line": pl.Int64, "competencia": pl.Utf8,
            "cnpj_empresa": pl.Utf8, "nome_empresa": pl.Utf8, "nf": pl.Int64,
            **{_norm(f): kinds.get(catalog.field_kind(f), pl.Utf8) for f in main[1:]}})
    sub = raw.filter(pl.col("reg") == reg)
    variants = catalog.LAYOUT_VARIANTS.get(TIPO, {}).get(reg, [])
    exprs = []
    for k, field in enumerate(main[1:], start=1):
        e = pl.col("f").list.get(k + 1, null_on_oob=True)
        for v in variants:
            e = pl.when(pl.col("nf") == len(v) - 1).then(
                pl.col("f").list.get(v.index(field) + 1, null_on_oob=True) if field in v else pl.lit(None, pl.Utf8)
            ).otherwise(e)
        exprs.append(_cast(e, catalog.field_kind(field)).alias(_norm(field)))
    return sub.select([pl.col(c) for c in base_cols] + exprs).sort(["file_id", "line_no"])


def _pair(raw: pl.DataFrame, key: str) -> pl.DataFrame:
    rp, rc = PAIRS[key]
    a = _reg(raw, rp).with_columns(pl.lit("PIS").alias("tributo"), pl.lit(rp).alias("reg"))
    b = _reg(raw, rc).with_columns(pl.lit("COFINS").alias("tributo"), pl.lit(rc).alias("reg"))
    return pl.concat([a, b], how="diagonal_relaxed")


def _asof(child: pl.DataFrame, parent: pl.DataFrame, cols: dict[str, str]) -> pl.DataFrame:
    """Liga cada linha filha à linha-pai imediatamente anterior no mesmo arquivo e tributo."""
    if child.height == 0:
        return child.with_columns([pl.lit(None, pl.Utf8).alias(v) for v in cols.values()])
    p = parent.select(["file_id", "tributo", pl.col("line_no").alias("parent_line")] +
                      [pl.col(k).alias(v) for k, v in cols.items()]).sort("parent_line")
    c = child.sort("line_no")
    if p.height == 0:
        return c.with_columns([pl.lit(None, pl.Utf8).alias(v) for v in cols.values()])
    return c.join_asof(p, left_on="line_no", right_on="parent_line", by=["file_id", "tributo"],
                       strategy="backward")


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


def _sum(df: pl.DataFrame, col: str) -> float:
    return _r(df[col].fill_null(0).sum()) if df.height and col in df.columns else 0.0


# --------------------------------------------------------------------------------------
# Visão geral
# --------------------------------------------------------------------------------------
def overview(db) -> dict:
    files = db.query("""
        SELECT a.id_arquivo, a.competencia, a.cnpj, a.nome, a.finalidade,
               EXISTS (SELECT 1 FROM linhas_contagem c WHERE c.file_id = a.id_arquivo) AS indexado,
               coalesce((SELECT sum(n) FROM linhas_contagem c WHERE c.file_id = a.id_arquivo AND c.reg LIKE 'M%'
                         AND c.reg NOT IN ('M001', 'M990')), 0) AS linhas_m
        FROM sys_arquivos_importados a WHERE a.ativo AND a.tipo_sped = ?
        ORDER BY a.competencia, a.cnpj""", [TIPO]).to_dicts()
    emp: dict[str, dict] = {}
    for f in files:
        e = emp.setdefault(f["cnpj"], {"cnpj": f["cnpj"], "nome": f["nome"], "competencias": []})
        e["competencias"].append(f["competencia"])
        e["nome"] = f["nome"] or e["nome"]
    return {"arquivos": files, "empresas": list(emp.values()),
            "competencias": sorted({f["competencia"] for f in files}),
            "pendentes": sum(1 for f in files if not f["indexado"]),
            "sem_bloco_m": sum(1 for f in files if f["indexado"] and not f["linhas_m"])}


# --------------------------------------------------------------------------------------
# Análise
# --------------------------------------------------------------------------------------
def analyze(db, q: dict) -> dict[str, pl.DataFrame | Any]:
    ids = file_ids(db, q)
    raw = _raw(db, ids)
    out: dict[str, Any] = {"ids": ids}

    # ---- consolidação (M200/M600)
    cons = _pair(raw, "consolidacao")
    out["consolidacao"] = cons

    # ---- créditos (M100/M500) e base (M105/M505)
    cred = _pair(raw, "credito").with_columns(
        pl.col("cod_cred").map_elements(T.cod_cred_desc, return_dtype=pl.Utf8).alias("cod_cred_desc"))
    out["credito"] = cred
    base = _pair(raw, "base_credito")
    par = cred.select(["file_id", "tributo", pl.col("line_no").alias("doc_line"), "cod_cred", pl.col("aliq").alias("aliq_cred")])
    base = base.join(par, on=["file_id", "tributo", "doc_line"], how="left").with_columns(
        pl.col("nat_bc_cred").map_elements(T.nat_desc, return_dtype=pl.Utf8).alias("nat_desc"),
        pl.col("cst").map_elements(T.cst_desc, return_dtype=pl.Utf8).alias("cst_desc"))
    out["base_credito"] = base

    # ---- contribuição (M210/M610) e códigos de receita (M205/M605)
    cont = _pair(raw, "contribuicao").with_columns(
        pl.col("cod_cont").map_elements(T.cod_cont_desc, return_dtype=pl.Utf8).alias("cod_cont_desc"),
        pl.when(pl.col("nf") <= 12).then(pl.lit("anterior a 2019")).otherwise(pl.lit("a partir de 2019"))
        .alias("leiaute"))
    out["contribuicao"] = cont
    rec = _pair(raw, "cod_receita").with_columns(
        pl.col("cod_rec").map_elements(T.cod_rec_desc, return_dtype=pl.Utf8).alias("cod_rec_desc"))
    out["cod_receita"] = rec

    # ---- ajustes
    aj_cred = _pair(raw, "aj_credito").join(
        cred.select(["file_id", "tributo", pl.col("line_no").alias("doc_line"), pl.col("cod_cred").alias("referencia")]),
        on=["file_id", "tributo", "doc_line"], how="left").with_columns(pl.lit("Crédito").alias("tipo"))
    aj_base = _asof(_pair(raw, "aj_base"), cont, {"cod_cont": "referencia"}).with_columns(
        pl.lit("Base de cálculo da contribuição").alias("tipo"))
    aj_cont = _asof(_pair(raw, "aj_contribuicao"), cont, {"cod_cont": "referencia"}).with_columns(
        pl.lit("Contribuição").alias("tipo"))
    cols = ["tributo", "tipo", "reg", "competencia", "cnpj_empresa", "nome_empresa", "referencia", "ind_aj", "vl_aj",
            "cod_aj", "num_doc", "descr_aj", "dt_ref", "file_id", "line_no"]
    frames = [f.select([c for c in cols if c in f.columns]) for f in (aj_cred, aj_base, aj_cont) if f.height]
    ajustes = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame(schema={c: pl.Utf8 for c in cols})
    if ajustes.height:
        ajustes = ajustes.with_columns(
            pl.col("ind_aj").replace_strict(T.IND_AJ, default=pl.col("ind_aj")).alias("ind_aj_desc"),
            pl.when(pl.col("ind_aj") == "0").then(-pl.col("vl_aj")).otherwise(pl.col("vl_aj")).alias("vl_aj_sinal"))
    out["ajustes"] = ajustes
    det_c = _asof(_pair(raw, "det_aj_credito"), _pair(raw, "aj_credito"), {"cod_aj": "cod_aj_pai"}).with_columns(
        pl.lit("Crédito").alias("tipo"))
    det_t = _asof(_pair(raw, "det_aj_contribuicao"), _pair(raw, "aj_contribuicao"), {"cod_aj": "cod_aj_pai"}
                  ).with_columns(pl.lit("Contribuição").alias("tipo"))
    frames = [f for f in (det_c, det_t) if f.height]
    out["det_ajustes"] = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()

    # ---- receitas não tributadas (M400/M800 + M410/M810)
    nt = _pair(raw, "receita_nt").with_columns(
        pl.col("cst").map_elements(T.cst_desc, return_dtype=pl.Utf8).alias("cst_desc"))
    out["receita_nt"] = nt
    nt_det = _pair(raw, "receita_nt_det").join(
        nt.select(["file_id", "tributo", pl.col("line_no").alias("doc_line"), "cst"]),
        on=["file_id", "tributo", "doc_line"], how="left")
    out["receita_nt_det"] = nt_det

    # ---- saldos de créditos (1100/1500)
    sal = _pair(raw, "saldo").with_columns(
        pl.col("cod_cred").map_elements(T.cod_cred_desc, return_dtype=pl.Utf8).alias("cod_cred_desc"),
        (pl.col("per_apu_cred").str.slice(2, 4) + "-" + pl.col("per_apu_cred").str.slice(0, 2)).alias("periodo_origem"))
    out["saldo"] = sal

    out["conferencia"], out["conferencia_resumo"] = _conferencia(db, ids, base, cred)
    out["verificacoes"] = _checks(cons, cred, aj_cred, cont, aj_cont, rec, sal)
    out["leiaute"] = _layout_warnings(raw)
    out["kpis"] = _kpis(cons, cred, sal)
    return out


# --------------------------------------------------------------------------------------
# Conferência: bases de crédito do M105/M505 x documentos da própria escrituração
# --------------------------------------------------------------------------------------
_DOC_SQL = """
WITH d AS (
    SELECT file_id, doc_id, reg FROM ec_doc
    WHERE file_id IN ({ids}) AND coalesce(cod_sit, '00') NOT IN ({cod_sit})
), src AS (
    -- C170 (sem natureza no registro: derivada do CFOP) e A170 (natureza informada)
    SELECT i.file_id, t.tributo, i.reg AS registro,
           coalesce(nullif(i.nat_bc_cred, ''), n.nat_bc_cred, '13') AS nat,
           (nullif(i.nat_bc_cred, '') IS NULL) AS derivada,
           CASE t.tributo WHEN 'PIS' THEN i.cst_pis ELSE i.cst_cofins END AS cst,
           CASE t.tributo WHEN 'PIS' THEN i.vl_bc_pis ELSE i.vl_bc_cofins END AS bc,
           CASE t.tributo WHEN 'PIS' THEN i.vl_pis ELSE i.vl_cofins END AS vl
    FROM ec_item i JOIN d ON d.file_id = i.file_id AND d.doc_id = i.doc_id
    CROSS JOIN (VALUES ('PIS'), ('COFINS')) t(tributo)
    LEFT JOIN ref_cfop_nat_bc_cred n ON n.cfop = i.cfop
    UNION ALL
    -- C191/C195 (consolidação de aquisições; natureza derivada do CFOP)
    SELECT x.file_id, x.tributo, x.reg, coalesce(n.nat_bc_cred, '13'), TRUE, x.cst, x.vl_bc, x.vl
    FROM ec_c191_195 x LEFT JOIN ref_cfop_nat_bc_cred n ON n.cfop = x.cfop
    WHERE x.file_id IN ({ids})
    UNION ALL
    -- C501/C505, D101/D105, D501/D505
    SELECT t.file_id, t.tributo, t.reg, coalesce(nullif(t.nat_bc_cred, ''), '13'), nullif(t.nat_bc_cred, '') IS NULL,
           t.cst, t.vl_bc, t.vl
    FROM ec_doc_trib t JOIN d ON d.file_id = t.file_id AND d.doc_id = t.doc_id
    UNION ALL
    -- F100 (operações com crédito), F120/F130 (ativo imobilizado)
    SELECT f.file_id, t.tributo, f.reg, coalesce(nullif(f.nat_bc_cred, ''), '13'), nullif(f.nat_bc_cred, '') IS NULL,
           CASE t.tributo WHEN 'PIS' THEN f.cst_pis ELSE f.cst_cofins END,
           CASE t.tributo WHEN 'PIS' THEN f.vl_bc_pis ELSE f.vl_bc_cofins END,
           CASE t.tributo WHEN 'PIS' THEN f.vl_pis ELSE f.vl_cofins END
    FROM ec_f f CROSS JOIN (VALUES ('PIS'), ('COFINS')) t(tributo)
    WHERE f.file_id IN ({ids})
)
SELECT file_id, tributo, nat AS nat_bc_cred, cst,
       CAST(sum(bc) AS DOUBLE) AS base_docs, CAST(sum(vl) AS DOUBLE) AS credito_docs,
       CAST(sum(bc) FILTER (WHERE derivada) AS DOUBLE) AS base_nat_derivada,
       string_agg(DISTINCT registro, ', ' ORDER BY registro) AS registros
FROM src WHERE cst IN ({cst})
GROUP BY ALL
"""


def _conferencia(db, ids: list[int], base: pl.DataFrame, cred: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    keys = ["file_id", "tributo", "nat_bc_cred", "cst"]
    if not ids:
        return pl.DataFrame(), pl.DataFrame()
    docs = db.query(_DOC_SQL.format(ids=",".join(map(str, ids)),
                                    cod_sit=", ".join(f"'{c}'" for c in config.COD_SIT_EXCLUIDOS),
                                    cst=", ".join(f"'{c}'" for c in config.CST_PIS_COFINS_CREDITO)))
    docs = docs.with_columns(pl.col("file_id").cast(pl.Int64))
    # Bloco M: base total escriturada por natureza/CST. Para CST de rateio (53-56, 63-66) a base total se repete em
    # cada tipo de crédito (1xx/2xx/3xx) — é contada uma vez por tipo de alíquota (2 últimos dígitos do COD_CRED).
    if base.height:
        b = base.with_columns(pl.col("file_id").cast(pl.Int64),
                              pl.col("cod_cred").fill_null("").str.slice(1, 2).alias("tipo_cred"),
                              pl.col("cst").is_in(list(T.CST_RATEIO)).alias("rateio"))
        uniq = b.filter(pl.col("rateio")).group_by(keys + ["tipo_cred", "aliq_cred"]).agg(
            pl.col("vl_bc_tot").max().alias("base_m"))
        plain = b.filter(~pl.col("rateio")).select(keys + [pl.col("vl_bc_tot").alias("base_m")])
        m = pl.concat([uniq.select(keys + ["base_m"]), plain], how="vertical_relaxed").group_by(keys).agg(
            pl.col("base_m").sum())
    else:
        m = pl.DataFrame(schema={"file_id": pl.Int64, "tributo": pl.Utf8, "nat_bc_cred": pl.Utf8, "cst": pl.Utf8,
                                 "base_m": pl.Float64})
    det = docs.join(m, on=keys, how="full", coalesce=True).with_columns(
        pl.col("base_docs").fill_null(0), pl.col("credito_docs").fill_null(0), pl.col("base_m").fill_null(0))
    if det.height == 0:
        return det, det
    meta = db.query(f"SELECT id_arquivo AS file_id, competencia, cnpj AS cnpj_empresa, nome AS nome_empresa "
                    f"FROM sys_arquivos_importados WHERE id_arquivo IN ({','.join(map(str, ids))})").with_columns(
        pl.col("file_id").cast(pl.Int64))
    det = det.join(meta, on="file_id", how="left").with_columns(
        ((pl.col("base_m") - pl.col("base_docs")).round(2) + 0.0).alias("diferenca"),
        pl.col("nat_bc_cred").map_elements(T.nat_desc, return_dtype=pl.Utf8).alias("nat_desc"),
        pl.col("cst").map_elements(T.cst_desc, return_dtype=pl.Utf8).alias("cst_desc"),
    ).sort(["competencia", "cnpj_empresa", "tributo", "nat_bc_cred", "cst"])
    cr = cred.with_columns(pl.col("file_id").cast(pl.Int64)).group_by(["file_id", "tributo"]).agg(
        pl.col("vl_cred").fill_null(0).sum().alias("credito_m"))
    res = det.group_by(["file_id", "competencia", "cnpj_empresa", "nome_empresa", "tributo"]).agg(
        pl.col("base_docs").sum(), pl.col("base_m").sum(), pl.col("credito_docs").sum(),
        pl.col("base_nat_derivada").fill_null(0).sum()
    ).join(cr, on=["file_id", "tributo"], how="left").with_columns(
        pl.col("credito_m").fill_null(0),
        ((pl.col("base_m") - pl.col("base_docs")).round(2) + 0.0).alias("diferenca_base"),
    ).with_columns(((pl.col("credito_m") - pl.col("credito_docs")).round(2) + 0.0).alias("diferenca_credito")
                   ).sort(["competencia", "cnpj_empresa", "tributo"])
    return det, res


# --------------------------------------------------------------------------------------
# Verificações aritméticas entre os registros
# --------------------------------------------------------------------------------------
def _checks(cons, cred, aj_cred, cont, aj_cont, rec, sal) -> pl.DataFrame:
    rows: list[dict] = []

    def add(r: dict, trib: str, desc: str, esperado: float, informado: float, reg: str) -> None:
        dif = round(informado - esperado, 2) + 0.0
        rows.append({"competencia": r["competencia"], "cnpj_empresa": r["cnpj_empresa"],
                     "nome_empresa": r["nome_empresa"], "tributo": trib, "registro": reg, "verificacao": desc,
                     "esperado": round(esperado, 2), "informado": round(informado, 2), "diferenca": dif,
                     "status": "OK" if abs(dif) <= TOL else "Divergente"})

    def by(df: pl.DataFrame, fid: int, trib: str) -> pl.DataFrame:
        if df.height == 0:
            return df
        return df.filter((pl.col("file_id") == fid) & (pl.col("tributo") == trib))

    for r in cons.to_dicts():
        fid, trib = r["file_id"], r["tributo"]
        rc, rcred = ("M200", "M100") if trib == "PIS" else ("M600", "M500")
        c = by(cred, fid, trib)
        add(r, trib, f"Crédito descontado do período = soma do VL_CRED_DESC dos {rcred}",
            _sum(c, "vl_cred_desc"), _r(r["vl_tot_cred_desc"]), rc)
        s = by(sal, fid, trib)
        add(r, trib, f"Crédito de períodos anteriores descontado = soma do VL_CRED_DESC_EFD dos "
                     f"{'1100' if trib == 'PIS' else '1500'}", _sum(s, "vl_cred_desc_efd"),
            _r(r["vl_tot_cred_desc_ant"]), rc)
        add(r, trib, "Contribuição não cumulativa devida = apurada − créditos do período − créditos anteriores",
            _r(r["vl_tot_cont_nc_per"]) - _r(r["vl_tot_cred_desc"]) - _r(r["vl_tot_cred_desc_ant"]),
            _r(r["vl_tot_cont_nc_dev"]), rc)
        add(r, trib, "Não cumulativa a recolher = devida − retenções − outras deduções",
            _r(r["vl_tot_cont_nc_dev"]) - _r(r["vl_ret_nc"]) - _r(r["vl_out_ded_nc"]), _r(r["vl_cont_nc_rec"]), rc)
        add(r, trib, "Cumulativa a recolher = apurada − retenções − outras deduções",
            _r(r["vl_tot_cont_cum_per"]) - _r(r["vl_ret_cum"]) - _r(r["vl_out_ded_cum"]), _r(r["vl_cont_cum_rec"]), rc)
        add(r, trib, "Total a recolher = não cumulativa a recolher + cumulativa a recolher",
            _r(r["vl_cont_nc_rec"]) + _r(r["vl_cont_cum_rec"]), _r(r["vl_tot_cont_rec"]), rc)
        rr = by(rec, fid, trib)
        if rr.height or _r(r["vl_tot_cont_rec"]):
            add(r, trib, f"Soma dos débitos por código de receita ({'M205' if trib == 'PIS' else 'M605'}) = total a recolher",
                _r(r["vl_tot_cont_rec"]), _sum(rr, "vl_debito"), "M205" if trib == "PIS" else "M605")

    for r in cred.to_dicts():
        trib, reg = r["tributo"], r["reg"]
        ref = f"{reg} {r['cod_cred'] or ''}".strip()
        add(r, trib, f"{ref}: crédito disponível = apurado + ajustes de acréscimo − ajustes de redução − diferido",
            _r(r["vl_cred"]) + _r(r["vl_ajus_acres"]) - _r(r["vl_ajus_reduc"]) - _r(r["vl_cred_dif"]),
            _r(r["vl_cred_disp"]), reg)
        add(r, trib, f"{ref}: saldo a utilizar = disponível − descontado no período",
            _r(r["vl_cred_disp"]) - _r(r["vl_cred_desc"]), _r(r["sld_cred"]), reg)
        a = aj_cred.filter((pl.col("file_id") == r["file_id"]) & (pl.col("tributo") == trib) &
                           (pl.col("doc_line") == r["line_no"])) if aj_cred.height else aj_cred
        if a.height or _r(r["vl_ajus_acres"]) or _r(r["vl_ajus_reduc"]):
            reg_aj = "M110" if trib == "PIS" else "M510"
            add(r, trib, f"{ref}: ajustes de acréscimo = soma dos {reg_aj} de acréscimo",
                _sum(a.filter(pl.col("ind_aj") == "1") if a.height else a, "vl_aj"), _r(r["vl_ajus_acres"]), reg)
            add(r, trib, f"{ref}: ajustes de redução = soma dos {reg_aj} de redução",
                _sum(a.filter(pl.col("ind_aj") == "0") if a.height else a, "vl_aj"), _r(r["vl_ajus_reduc"]), reg)

    for r in cont.to_dicts():
        trib, reg = r["tributo"], r["reg"]
        ref = f"{reg} {r['cod_cont'] or ''}".strip()
        add(r, trib, f"{ref}: contribuição do período = apurada + acréscimos − reduções − diferida + diferida de "
                     f"períodos anteriores",
            _r(r["vl_cont_apur"]) + _r(r["vl_ajus_acres"]) - _r(r["vl_ajus_reduc"]) - _r(r["vl_cont_difer"])
            + _r(r["vl_cont_difer_ant"]), _r(r["vl_cont_per"]), reg)
        a = aj_cont.filter((pl.col("file_id") == r["file_id"]) & (pl.col("tributo") == trib) &
                           (pl.col("parent_line") == r["line_no"])) if aj_cont.height else aj_cont
        if a.height or _r(r["vl_ajus_acres"]) or _r(r["vl_ajus_reduc"]):
            reg_aj = "M220" if trib == "PIS" else "M620"
            add(r, trib, f"{ref}: acréscimos = soma dos {reg_aj} de acréscimo",
                _sum(a.filter(pl.col("ind_aj") == "1") if a.height else a, "vl_aj"), _r(r["vl_ajus_acres"]), reg)
            add(r, trib, f"{ref}: reduções = soma dos {reg_aj} de redução",
                _sum(a.filter(pl.col("ind_aj") == "0") if a.height else a, "vl_aj"), _r(r["vl_ajus_reduc"]), reg)

    for r in cons.to_dicts():   # contribuição apurada no M200/M600 x soma dos M210/M610 (total NC + cumulativa)
        trib = r["tributo"]
        c = by(cont, r["file_id"], trib)
        if c.height:
            add(r, trib, f"Contribuição do período (não cumulativa + cumulativa) = soma do VL_CONT_PER dos "
                         f"{'M210' if trib == 'PIS' else 'M610'}",
                _sum(c, "vl_cont_per"), _r(r["vl_tot_cont_nc_per"]) + _r(r["vl_tot_cont_cum_per"]),
                "M200" if trib == "PIS" else "M600")

    for r in sal.to_dicts():
        trib, reg = r["tributo"], r["reg"]
        ref = f"{reg} {r['periodo_origem']} {r['cod_cred'] or ''}"
        add(r, trib, f"{ref}: saldo disponível = total apurado − utilizado em períodos anteriores (desconto, "
                     f"ressarcimento e compensação)",
            _r(r["vl_tot_cred_apu"]) - _r(r["vl_cred_desc_pa_ant"]) - _r(r["vl_cred_per_pa_ant"])
            - _r(r["vl_cred_dcomp_pa_ant"]), _r(r["sd_cred_disp_efd"]), reg)
        add(r, trib, f"{ref}: saldo final = disponível − utilizado nesta escrituração − transferido − outras formas",
            _r(r["sd_cred_disp_efd"]) - _r(r["vl_cred_desc_efd"]) - _r(r["vl_cred_per_efd"])
            - _r(r["vl_cred_dcomp_efd"]) - _r(r["vl_cred_trans"]) - _r(r["vl_cred_out"]), _r(r["sld_cred_fim"]), reg)

    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).sort(["status", "competencia", "cnpj_empresa", "tributo"], descending=[False, False, False, True])


def _layout_warnings(raw: pl.DataFrame) -> list[dict]:
    if raw.height == 0:
        return []
    out = []
    for (reg,), g in raw.group_by(["reg"]):
        ok = {len(catalog.LAYOUTS[TIPO][reg]) - 1} | {len(v) - 1 for v in catalog.LAYOUT_VARIANTS[TIPO].get(reg, [])}
        bad = g.filter(~pl.col("nf").is_in(list(ok)))
        if bad.height:
            out.append({"reg": reg, "linhas": bad.height, "campos_encontrados": sorted(set(bad["nf"].to_list())),
                        "campos_esperados": sorted(ok)})
    return sorted(out, key=lambda x: x["reg"])


def _kpis(cons: pl.DataFrame, cred: pl.DataFrame, sal: pl.DataFrame) -> dict:
    out = {}
    for trib in ("PIS", "COFINS"):
        c = cons.filter(pl.col("tributo") == trib) if cons.height else cons
        cr = cred.filter(pl.col("tributo") == trib) if cred.height else cred
        s = sal.filter(pl.col("tributo") == trib) if sal.height else sal
        # saldo de créditos ao final do último período selecionado de cada empresa
        saldo = 0.0
        if c.height:
            last = c.group_by("cnpj_empresa").agg(pl.col("competencia").max())
            for e in last.to_dicts():
                key = (pl.col("cnpj_empresa") == e["cnpj_empresa"]) & (pl.col("competencia") == e["competencia"])
                saldo += _sum(cr.filter(key) if cr.height else cr, "sld_cred")
                saldo += _sum(s.filter(key) if s.height else s, "sld_cred_fim")
        out[trib] = {
            "contribuicao": _sum(c, "vl_tot_cont_nc_per") + _sum(c, "vl_tot_cont_cum_per"),
            "contribuicao_nc": _sum(c, "vl_tot_cont_nc_per"), "contribuicao_cum": _sum(c, "vl_tot_cont_cum_per"),
            "creditos_apurados": _sum(cr, "vl_cred"),
            "ajustes_credito": _sum(cr, "vl_ajus_acres") - _sum(cr, "vl_ajus_reduc"),
            "creditos_disponiveis": _sum(cr, "vl_cred_disp"),
            "creditos_descontados": _sum(c, "vl_tot_cred_desc"),
            "creditos_anteriores": _sum(c, "vl_tot_cred_desc_ant"),
            "retencoes": _sum(c, "vl_ret_nc") + _sum(c, "vl_ret_cum"),
            "outras_deducoes": _sum(c, "vl_out_ded_nc") + _sum(c, "vl_out_ded_cum"),
            "a_recolher": _sum(c, "vl_tot_cont_rec"),
            "saldo_credito": round(saldo, 2),
        }
    return out


# --------------------------------------------------------------------------------------
# Rótulos (tela e Excel)
# --------------------------------------------------------------------------------------
LABELS = {
    "competencia": "Competência", "cnpj_empresa": "CNPJ (0000)", "nome_empresa": "Empresa", "tributo": "Tributo",
    "reg": "Registro", "registro": "Registro", "file_id": "Arquivo (ID)", "line_no": "Linha no arquivo",
    "cod_cred": "Tipo de crédito (COD_CRED)", "cod_cred_desc": "Descrição do tipo de crédito",
    "ind_cred_ori": "Origem do crédito (IND_CRED_ORI)", "vl_bc": "Base de cálculo", "aliq": "Alíquota (%)",
    "quant_bc": "Quantidade (base)", "aliq_quant": "Alíquota (R$/unid.)", "vl_cred": "Crédito apurado",
    "vl_ajus_acres": "Ajustes de acréscimo", "vl_ajus_reduc": "Ajustes de redução", "vl_cred_dif": "Crédito diferido",
    "vl_cred_disp": "Crédito disponível", "ind_desc_cred": "Utilização (IND_DESC_CRED)",
    "vl_cred_desc": "Crédito descontado no período", "sld_cred": "Saldo a utilizar em períodos futuros",
    "nat_bc_cred": "Natureza da base (NAT_BC_CRED)", "nat_desc": "Descrição da natureza", "cst": "CST",
    "cst_desc": "Descrição do CST", "vl_bc_tot": "Base total escriturada", "vl_bc_cum": "Parcela da base – cumulativo",
    "vl_bc_nc": "Parcela da base – não cumulativo", "quant_bc_tot": "Quantidade total (base)",
    "desc_cred": "Descrição do crédito", "aliq_cred": "Alíquota do crédito (%)",
    "vl_tot_cont_nc_per": "Contribuição não cumulativa do período", "vl_tot_cred_desc": "(−) Créditos descontados do período",
    "vl_tot_cred_desc_ant": "(−) Créditos de períodos anteriores", "vl_tot_cont_nc_dev": "= Contribuição não cumulativa devida",
    "vl_ret_nc": "(−) Retenções na fonte (não cumulativa)", "vl_out_ded_nc": "(−) Outras deduções (não cumulativa)",
    "vl_cont_nc_rec": "= Não cumulativa a recolher", "vl_tot_cont_cum_per": "Contribuição cumulativa do período",
    "vl_ret_cum": "(−) Retenções na fonte (cumulativa)", "vl_out_ded_cum": "(−) Outras deduções (cumulativa)",
    "vl_cont_cum_rec": "= Cumulativa a recolher", "vl_tot_cont_rec": "TOTAL A RECOLHER",
    "num_campo": "Campo do M200/M600", "cod_rec": "Código de receita", "cod_rec_desc": "Descrição do código",
    "vl_debito": "Valor do débito", "cod_cont": "Código da contribuição (COD_CONT)", "cod_cont_desc": "Descrição",
    "vl_rec_brt": "Receita bruta", "vl_bc_cont": "Base de cálculo", "vl_ajus_acres_bc": "Ajustes de acréscimo da base",
    "vl_ajus_reduc_bc": "Ajustes de redução da base", "vl_bc_cont_ajus": "Base de cálculo ajustada",
    "vl_cont_apur": "Contribuição apurada", "vl_cont_difer": "Contribuição diferida",
    "vl_cont_difer_ant": "Diferida de períodos anteriores", "vl_cont_per": "Contribuição do período", "leiaute": "Leiaute",
    "tipo": "Tipo de ajuste", "referencia": "Referência (COD_CRED / COD_CONT)", "ind_aj": "Indicador (IND_AJ)",
    "ind_aj_desc": "Acréscimo / redução", "vl_aj": "Valor do ajuste", "vl_aj_sinal": "Valor com sinal",
    "cod_aj": "Código do ajuste", "num_doc": "Documento / processo", "descr_aj": "Descrição do ajuste",
    "dt_ref": "Data de referência", "det_valor_aj": "Valor detalhado", "det_bc_cred": "Base detalhada",
    "det_aliq": "Alíquota detalhada", "dt_oper_aj": "Data da operação", "desc_aj": "Descrição", "cod_cta": "Conta contábil",
    "info_compl": "Informação complementar", "cod_aj_pai": "Código do ajuste (pai)", "vl_tot_rec": "Receita total",
    "desc_compl": "Descrição complementar", "nat_rec": "Natureza da receita (NAT_REC)", "vl_rec": "Valor da receita",
    "periodo_origem": "Período de origem do crédito", "per_apu_cred": "PER_APU_CRED", "orig_cred": "Origem (ORIG_CRED)",
    "cnpj_suc": "CNPJ da sucedida", "vl_cred_apu": "Crédito apurado na origem", "vl_cred_ext_apu": "Crédito extemporâneo",
    "vl_tot_cred_apu": "Total apurado", "vl_cred_desc_pa_ant": "Descontado em períodos anteriores",
    "vl_cred_per_pa_ant": "Ressarcido em períodos anteriores", "vl_cred_dcomp_pa_ant": "Compensado (PER/DCOMP) antes",
    "sd_cred_disp_efd": "Saldo disponível nesta escrituração", "vl_cred_desc_efd": "Descontado nesta escrituração",
    "vl_cred_per_efd": "Pedido de ressarcimento nesta escrituração", "vl_cred_dcomp_efd": "Compensação nesta escrituração",
    "vl_cred_trans": "Transferido (cisão/fusão/incorporação)", "vl_cred_out": "Utilizado de outras formas",
    "sld_cred_fim": "Saldo final a utilizar", "base_docs": "Base nos documentos (A, C, D, F)",
    "base_m": "Base no Bloco M (M105/M505)", "diferenca": "Diferença (Bloco M − documentos)",
    "credito_docs": "Crédito nos documentos", "base_nat_derivada": "Base com natureza derivada do CFOP",
    "registros": "Registros de origem", "credito_m": "Crédito apurado (M100/M500)",
    "diferenca_base": "Diferença de base", "diferenca_credito": "Diferença de crédito",
    "verificacao": "Verificação", "esperado": "Valor esperado (calculado)", "informado": "Valor informado",
    "status": "Situação", "doc_line": "Linha do registro-pai", "parent_line": "Linha do ajuste (pai)",
}

SECTIONS = {   # chave -> (aba do Excel, colunas)
    "consolidacao": ("Apuração (M200-M600)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                     "vl_tot_cont_nc_per", "vl_tot_cred_desc", "vl_tot_cred_desc_ant", "vl_tot_cont_nc_dev",
                     "vl_ret_nc", "vl_out_ded_nc", "vl_cont_nc_rec", "vl_tot_cont_cum_per", "vl_ret_cum",
                     "vl_out_ded_cum", "vl_cont_cum_rec", "vl_tot_cont_rec", "file_id", "line_no"]),
    "credito": ("Créditos (M100-M500)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo", "cod_cred",
                "cod_cred_desc", "ind_cred_ori", "vl_bc", "aliq", "quant_bc", "aliq_quant", "vl_cred", "vl_ajus_acres",
                "vl_ajus_reduc", "vl_cred_dif", "vl_cred_disp", "ind_desc_cred", "vl_cred_desc", "sld_cred",
                "file_id", "line_no"]),
    "base_credito": ("Base créditos (M105-M505)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                     "cod_cred", "aliq_cred", "nat_bc_cred", "nat_desc", "cst", "cst_desc", "vl_bc_tot", "vl_bc_cum",
                     "vl_bc_nc", "vl_bc", "quant_bc_tot", "quant_bc", "desc_cred", "file_id", "line_no", "doc_line"]),
    "contribuicao": ("Contribuição (M210-M610)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                     "cod_cont", "cod_cont_desc", "vl_rec_brt", "vl_bc_cont", "vl_ajus_acres_bc", "vl_ajus_reduc_bc",
                     "vl_bc_cont_ajus", "aliq", "quant_bc", "aliq_quant", "vl_cont_apur", "vl_ajus_acres",
                     "vl_ajus_reduc", "vl_cont_difer", "vl_cont_difer_ant", "vl_cont_per", "leiaute", "file_id",
                     "line_no"]),
    "cod_receita": ("Códigos receita (M205-M605)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                    "num_campo", "cod_rec", "cod_rec_desc", "vl_debito", "file_id", "line_no"]),
    "ajustes": ("Ajustes", ["competencia", "cnpj_empresa", "nome_empresa", "tributo", "tipo", "reg", "referencia",
                "ind_aj_desc", "vl_aj", "vl_aj_sinal", "cod_aj", "num_doc", "descr_aj", "dt_ref", "file_id",
                "line_no"]),
    "det_ajustes": ("Detalhe ajustes", ["competencia", "cnpj_empresa", "nome_empresa", "tributo", "tipo", "reg",
                    "cod_aj_pai", "det_valor_aj", "cst", "det_bc_cred", "det_aliq", "dt_oper_aj", "desc_aj", "cod_cta",
                    "info_compl", "file_id", "line_no", "parent_line"]),
    "receita_nt": ("Receitas NT (M400-M800)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo", "cst",
                   "cst_desc", "vl_tot_rec", "cod_cta", "desc_compl", "file_id", "line_no"]),
    "receita_nt_det": ("Receitas NT det (M410-M810)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                       "cst", "nat_rec", "vl_rec", "cod_cta", "desc_compl", "file_id", "line_no", "doc_line"]),
    "saldo": ("Saldos créditos (1100-1500)", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
              "periodo_origem", "orig_cred", "cnpj_suc", "cod_cred", "cod_cred_desc", "vl_cred_apu", "vl_cred_ext_apu",
              "vl_tot_cred_apu", "vl_cred_desc_pa_ant", "vl_cred_per_pa_ant", "vl_cred_dcomp_pa_ant",
              "sd_cred_disp_efd", "vl_cred_desc_efd", "vl_cred_per_efd", "vl_cred_dcomp_efd", "vl_cred_trans",
              "vl_cred_out", "sld_cred_fim", "file_id", "line_no"]),
    "conferencia_resumo": ("Conferência resumo", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                           "base_docs", "base_m", "diferenca_base", "credito_docs", "credito_m", "diferenca_credito",
                           "base_nat_derivada"]),
    "conferencia": ("Conferência por natureza", ["competencia", "cnpj_empresa", "nome_empresa", "tributo",
                    "nat_bc_cred", "nat_desc", "cst", "cst_desc", "base_docs", "base_m", "diferenca", "credito_docs",
                    "base_nat_derivada", "registros"]),
    "verificacoes": ("Verificações", ["status", "competencia", "cnpj_empresa", "nome_empresa", "tributo", "registro",
                     "verificacao", "esperado", "informado", "diferenca"]),
}


def section(res: dict, key: str) -> pl.DataFrame:
    df = res.get(key)
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        return pl.DataFrame()
    cols = [c for c in SECTIONS[key][1] if c in df.columns]
    return df.select(cols)


def describe(q: dict) -> dict[str, str]:
    out = {"Fonte": "EFD-Contribuições — Bloco M e registros 1100/1500, valores como informados no arquivo"}
    if q.get("empresas"):
        out["Empresas (CNPJ)"] = ", ".join(q["empresas"])
    if q.get("comp_ini") or q.get("comp_fim"):
        out["Período"] = f"{q.get('comp_ini') or 'início'} a {q.get('comp_fim') or 'fim'}"
    out["Conferência"] = ("Base do M105/M505 (CST 50-56 e 60-66) x documentos da mesma escrituração: C170, A170, "
                          "C191/C195, C501/C505, D101/D105, D501/D505, F100, F120, F130. Natureza do C170 e do "
                          "C191/C195 derivada do CFOP. Não entram: C395/C396, F150, F200-F211, 1101/1501.")
    return out
