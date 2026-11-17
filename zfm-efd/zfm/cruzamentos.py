"""Cruzamentos EFD ICMS/IPI (Fiscal) × EFD Contribuicoes e cobertura das escrituracoes.

Mecanica (a mesma do Consolidador EFD):
- Empresa = raiz do CNPJ (a EFD Contribuicoes e da empresa; a Fiscal, de cada estabelecimento).
- Participante = CNPJ/CPF do 0150 de cada arquivo (COD_PART e codigo interno e nao e comparado).
- Documento = chave da NF-e (44 posicoes); sem chave, a chave composta
  estabelecimento | modelo | serie | numero | data | CNPJ do participante.
- O pareamento e por estabelecimento + sentido + chave: a NF-e de transferencia aparece como saida
  num estabelecimento e entrada em outro, e isso nao e repeticao.
- O mesmo documento escriturado mais de uma vez na mesma EFD (ex.: em dois periodos) conta uma
  vez: a primeira ocorrencia vale; as demais sao listadas como repetidas.
- Situacao do documento: nas duas EFDs / so numa / sem contrapartida (a outra EFD daquele
  periodo nao foi carregada) / Contribuicoes consolidada (C180/C190, sem documento).
- Itens: CFOPs do documento (C190 da Fiscal × C170 da Contribuicoes) e, quando as duas tem C170,
  item a item pelo NUM_ITEM (CFOP, codigo do item e valor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from . import params

CANCELADOS = "('02','03','04','05')"
NAS_DUAS = "Nas duas EFDs"
SO_FISCAL = "Só na EFD ICMS/IPI"
SO_FISCAL_ENTRADA = "Só na EFD ICMS/IPI (entrada sem crédito de PIS/COFINS?)"
SO_CONTRIB = "Só na EFD Contribuições"
SEM_CONTRIB = "Sem contrapartida: EFD Contribuições do mês não carregada"
SEM_FISCAL = "Sem contrapartida: EFD ICMS/IPI do estabelecimento/mês não carregada"
CONSOLIDADA = "Contribuições consolidada (C180/C190, sem documento)"
REPETIDO = "Repetido na mesma EFD (fora da contagem)"
SITUACOES_PROBLEMA = (SO_FISCAL, SO_CONTRIB)


def _tol() -> float:
    return params.premissa_num("tolerancia_conciliacao", 1.0)


# ---------------------------------------------------------------------------
# Documentos das duas EFDs com chave de pareamento
# ---------------------------------------------------------------------------
SQL_DOCS = f"""
WITH f AS (
    SELECT 'Fiscal' AS fonte, a.raiz, a.cnpj AS cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END AS sentido,
           d.COD_MOD AS cod_mod, d.SER AS ser, d.NUM_DOC AS num_doc, d.CHV_NFE AS chv_nfe, d.DT_DOC AS dt_doc,
           coalesce(nullif(p.cnpj_part, ''), nullif(p.cpf_part, ''), 'COD:' || d.COD_PART) AS participante,
           CAST(d.VL_DOC AS DOUBLE) AS vl_doc, CAST(d.VL_PIS AS DOUBLE) AS vl_pis,
           CAST(d.VL_COFINS AS DOUBLE) AS vl_cofins, d.arquivo_id, d.linha_num
    FROM raw_icms_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN v_participantes p ON p.arquivo_id = d.arquivo_id AND p.cod_part = d.COD_PART
    WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN {CANCELADOS}),
c AS (
    SELECT 'Contribuições', a.raiz, d.cnpj_estab, year(a.dt_ini), month(a.dt_ini),
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END,
           d.COD_MOD, d.SER, d.NUM_DOC, d.CHV_NFE, d.DT_DOC,
           coalesce(nullif(p.cnpj_part, ''), nullif(p.cpf_part, ''), 'COD:' || d.COD_PART),
           CAST(d.VL_DOC AS DOUBLE), CAST(d.VL_PIS AS DOUBLE), CAST(d.VL_COFINS AS DOUBLE),
           d.arquivo_id, d.linha_num
    FROM raw_contrib_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN v_participantes_contrib p ON p.arquivo_id = d.arquivo_id AND p.cnpj_estab = d.cnpj_estab
         AND p.cod_part = d.COD_PART
    WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN {CANCELADOS}),
u AS (
    SELECT *, CASE WHEN regexp_full_match(upper(coalesce(chv_nfe, '')), '[0-9A-Z]{{44}}') THEN upper(chv_nfe)
                   ELSE 'K|' || cnpj_estab || '|' || coalesce(cod_mod, '') || '|' || coalesce(ser, '') || '|'
                        || coalesce(ltrim(num_doc, '0'), '') || '|' || coalesce(strftime(dt_doc, '%Y%m%d'), '')
                        || '|' || participante END AS chave
    FROM (SELECT * FROM f UNION ALL SELECT * FROM c)),
o AS (
    SELECT *, row_number() OVER (PARTITION BY fonte, cnpj_estab, sentido, chave
                                 ORDER BY ano, mes, arquivo_id, linha_num) AS ocorrencia,
              count(*) OVER (PARTITION BY fonte, cnpj_estab, sentido, chave) AS n_ocorrencias
    FROM u),
fontes AS (
    SELECT cnpj_estab, sentido, chave, bool_or(fonte = 'Fiscal') AS tf, bool_or(fonte = 'Contribuições') AS tc
    FROM o WHERE ocorrencia = 1 GROUP BY ALL),
cobf AS (SELECT DISTINCT cnpj, year(dt_ini) AS ano, month(dt_ini) AS mes FROM arquivos
         WHERE ativo AND tipo = 'ICMS_IPI'),
cobc AS (SELECT DISTINCT raiz, year(dt_ini) AS ano, month(dt_ini) AS mes FROM arquivos
         WHERE ativo AND tipo = 'CONTRIB'),
cons AS (SELECT DISTINCT x.cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes
         FROM raw_contrib_c010 x JOIN arquivos a USING (arquivo_id)
         WHERE a.ativo AND x.IND_ESCRI = '1'),
docs AS (
    SELECT o.*,
           CASE WHEN o.ocorrencia > 1 THEN '{REPETIDO}'
                WHEN fo.tf AND fo.tc THEN '{NAS_DUAS}'
                WHEN o.fonte = 'Fiscal' AND cc.raiz IS NULL THEN '{SEM_CONTRIB}'
                WHEN o.fonte = 'Fiscal' AND co.cnpj_estab IS NOT NULL THEN '{CONSOLIDADA}'
                WHEN o.fonte = 'Fiscal' AND o.sentido = 'entrada' THEN '{SO_FISCAL_ENTRADA}'
                WHEN o.fonte = 'Fiscal' THEN '{SO_FISCAL}'
                WHEN cf.cnpj IS NULL THEN '{SEM_FISCAL}'
                ELSE '{SO_CONTRIB}' END AS situacao
    FROM o
    LEFT JOIN fontes fo ON fo.cnpj_estab = o.cnpj_estab AND fo.sentido = o.sentido AND fo.chave = o.chave
    LEFT JOIN cobc cc ON cc.raiz = o.raiz AND cc.ano = o.ano AND cc.mes = o.mes
    LEFT JOIN cobf cf ON cf.cnpj = o.cnpj_estab AND cf.ano = o.ano AND cf.mes = o.mes
    LEFT JOIN cons co ON co.cnpj_estab = o.cnpj_estab AND co.ano = o.ano AND co.mes = o.mes)
"""


def documentos(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(SQL_DOCS + """
        SELECT fonte, situacao, sentido, raiz, cnpj_estab, ano, mes, cod_mod, ser, num_doc, chv_nfe, dt_doc,
               participante, vl_doc, vl_pis, vl_cofins, ocorrencia, n_ocorrencias, arquivo_id, linha_num, chave
        FROM docs""").df()


def resumo_pareamento(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Documentos por fonte, sentido e situacao (quantidade e valor)."""
    return con.execute(SQL_DOCS + """
        SELECT raiz, fonte, sentido, situacao, count(*) AS documentos, sum(vl_doc) AS valor
        FROM docs GROUP BY ALL ORDER BY raiz, fonte, sentido, situacao""").df()


def pareamento_divergencias(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """R4: documento so numa EFD (com as duas carregadas) ou com cabecalho diferente nas duas."""
    tol = _tol()
    so_um = con.execute(SQL_DOCS + f"""
        SELECT raiz, cnpj_estab, mes, sentido, fonte, situacao AS problema, num_doc, chv_nfe, participante,
               vl_doc AS valor_fiscal_ou_contrib, NULL::DOUBLE AS valor_outra_efd, arquivo_id, linha_num
        FROM docs WHERE situacao IN ('{SO_FISCAL}', '{SO_CONTRIB}')""").df()
    dif = con.execute(SQL_DOCS + f"""
        , p AS (SELECT * FROM docs WHERE ocorrencia = 1 AND situacao = '{NAS_DUAS}')
        SELECT f.raiz, f.cnpj_estab, f.mes, f.sentido, 'Fiscal × Contribuições' AS fonte,
               concat_ws('; ',
                   CASE WHEN abs(coalesce(f.vl_doc, 0) - coalesce(c.vl_doc, 0)) > {tol} THEN 'valor do documento' END,
                   CASE WHEN f.dt_doc IS DISTINCT FROM c.dt_doc THEN 'data' END,
                   CASE WHEN f.participante <> c.participante AND f.participante NOT LIKE 'COD:%'
                             AND c.participante NOT LIKE 'COD:%' THEN 'participante (CNPJ)' END,
                   CASE WHEN f.sentido = 'saida' AND (abs(coalesce(f.vl_pis, 0) - coalesce(c.vl_pis, 0)) > {tol}
                             OR abs(coalesce(f.vl_cofins, 0) - coalesce(c.vl_cofins, 0)) > {tol})
                        THEN 'PIS/COFINS' END) AS problema,
               f.num_doc, f.chv_nfe, f.participante, f.vl_doc, c.vl_doc, f.arquivo_id, f.linha_num
        FROM (SELECT * FROM p WHERE fonte = 'Fiscal') f
        JOIN (SELECT * FROM p WHERE fonte = 'Contribuições') c
          ON c.cnpj_estab = f.cnpj_estab AND c.sentido = f.sentido AND c.chave = f.chave
        WHERE abs(coalesce(f.vl_doc, 0) - coalesce(c.vl_doc, 0)) > {tol} OR f.dt_doc IS DISTINCT FROM c.dt_doc
           OR (f.participante <> c.participante AND f.participante NOT LIKE 'COD:%' AND c.participante NOT LIKE 'COD:%')
           OR (f.sentido = 'saida' AND (abs(coalesce(f.vl_pis, 0) - coalesce(c.vl_pis, 0)) > {tol}
               OR abs(coalesce(f.vl_cofins, 0) - coalesce(c.vl_cofins, 0)) > {tol}))""").df()
    if not dif.empty:
        dif["problema"] = "Diferente nas duas EFDs: " + dif["problema"]
    dif.columns = so_um.columns
    return pd.concat([so_um, dif], ignore_index=True)


def divergencias_itens(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Documentos nas duas EFDs: CFOP so de um lado (C190 da Fiscal × C170 da Contribuicoes) e itens
    (mesmo NUM_ITEM) com CFOP, codigo do item ou valor diferentes. O CFOP liga o produto (Contribuicoes)
    ao destino (C190 + 0150 da Fiscal); CFOP diferente leva o destino ao rateio ou a regra geral."""
    tol = _tol()
    return con.execute(SQL_DOCS + f"""
        , p AS (SELECT * FROM docs WHERE ocorrencia = 1 AND situacao = '{NAS_DUAS}'),
        fcfop AS (SELECT p.raiz, p.cnpj_estab || p.sentido || p.chave AS chave, c.CFOP AS cfop, sum(CAST(c.VL_OPR AS DOUBLE)) AS v
                  FROM p JOIN raw_icms_c190 c ON c.arquivo_id = p.arquivo_id AND c.pai_linha = p.linha_num
                  WHERE p.fonte = 'Fiscal' GROUP BY ALL),
        ccfop AS (SELECT p.raiz, p.cnpj_estab || p.sentido || p.chave AS chave, i.CFOP AS cfop, sum(CAST(i.VL_ITEM - coalesce(i.VL_DESC, 0) AS DOUBLE)) AS v
                  FROM p JOIN raw_contrib_c170 i ON i.arquivo_id = p.arquivo_id AND i.pai_linha = p.linha_num
                  WHERE p.fonte = 'Contribuições' GROUP BY ALL),
        cf AS (
            SELECT coalesce(a.raiz, b.raiz) AS raiz, coalesce(a.chave, b.chave) AS chave,
                   coalesce(a.cfop, b.cfop) AS cfop, a.v AS valor_fiscal, b.v AS valor_contrib,
                   CASE WHEN b.cfop IS NULL THEN 'CFOP só na EFD ICMS/IPI (C190)'
                        ELSE 'CFOP só na EFD Contribuições (C170)' END AS problema
            FROM fcfop a FULL JOIN ccfop b ON a.raiz = b.raiz AND a.chave = b.chave AND a.cfop = b.cfop
            WHERE a.cfop IS NULL OR b.cfop IS NULL),
        cf_ok AS (SELECT * FROM cf WHERE chave IN (SELECT chave FROM ccfop) AND chave IN (SELECT chave FROM fcfop)),
        fi AS (SELECT p.raiz, p.cnpj_estab || p.sentido || p.chave AS chave, i.NUM_ITEM AS num_item, any_value(i.CFOP) AS cfop, any_value(i.COD_ITEM) AS cod_item,
                      any_value(CAST(i.VL_ITEM AS DOUBLE)) AS vl_item
               FROM p JOIN raw_icms_c170 i ON i.arquivo_id = p.arquivo_id AND i.pai_linha = p.linha_num
               WHERE p.fonte = 'Fiscal' GROUP BY ALL HAVING count(*) = 1),
        ci AS (SELECT p.raiz, p.cnpj_estab || p.sentido || p.chave AS chave, i.NUM_ITEM AS num_item, any_value(i.CFOP) AS cfop, any_value(i.COD_ITEM) AS cod_item,
                      any_value(CAST(i.VL_ITEM AS DOUBLE)) AS vl_item
               FROM p JOIN raw_contrib_c170 i ON i.arquivo_id = p.arquivo_id AND i.pai_linha = p.linha_num
               WHERE p.fonte = 'Contribuições' GROUP BY ALL HAVING count(*) = 1),
        it AS (
            SELECT fi.raiz, fi.chave, fi.cfop, fi.vl_item AS valor_fiscal, ci.vl_item AS valor_contrib,
                   'Item ' || fi.num_item || ' diferente: ' || concat_ws(', ',
                       CASE WHEN fi.cfop <> ci.cfop THEN 'CFOP ' || fi.cfop || ' × ' || ci.cfop END,
                       CASE WHEN fi.cod_item <> ci.cod_item THEN 'produto ' || fi.cod_item || ' × ' || ci.cod_item END,
                       CASE WHEN abs(fi.vl_item - ci.vl_item) > {tol} THEN 'valor' END) AS problema
            FROM fi JOIN ci ON ci.raiz = fi.raiz AND ci.chave = fi.chave AND ci.num_item = fi.num_item
            WHERE fi.cfop <> ci.cfop OR fi.cod_item <> ci.cod_item OR abs(fi.vl_item - ci.vl_item) > {tol}),
        x AS (SELECT * FROM cf_ok UNION ALL BY NAME SELECT * FROM it)
        SELECT f.raiz, f.cnpj_estab, f.mes, f.sentido, x.problema, x.cfop, f.num_doc, f.chv_nfe,
               x.valor_fiscal, x.valor_contrib, f.arquivo_id, f.linha_num
        FROM x JOIN (SELECT * FROM p WHERE fonte = 'Fiscal') f
          ON f.cnpj_estab || f.sentido || f.chave = x.chave
        ORDER BY 1, 2, 3""").df()


def repetidos(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Mesmo documento escriturado mais de uma vez na mesma EFD (ex.: em dois periodos)."""
    return con.execute(SQL_DOCS + """
        SELECT raiz, cnpj_estab, mes, sentido, fonte, num_doc, chv_nfe, participante, vl_doc, ocorrencia,
               n_ocorrencias, CASE WHEN ocorrencia = 1 THEN 'Primeira ocorrência' ELSE 'Repetição' END AS situacao,
               arquivo_id, linha_num
        FROM docs WHERE n_ocorrencias > 1 ORDER BY raiz, cnpj_estab, chave, ocorrencia""").df()


def c170_x_c190(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """EFD ICMS/IPI: soma dos itens C170 × analitico C190, por documento e CFOP."""
    tol = _tol()
    return con.execute(f"""
        WITH i AS (SELECT arquivo_id, pai_linha, CFOP AS cfop, sum(coalesce(VL_BC_ICMS, 0)) AS bc,
                          sum(coalesce(VL_ICMS, 0)) AS icms, sum(coalesce(VL_IPI, 0)) AS ipi
                   FROM raw_icms_c170 GROUP BY ALL),
             a AS (SELECT arquivo_id, pai_linha, CFOP AS cfop, sum(coalesce(VL_BC_ICMS, 0)) AS bc,
                          sum(coalesce(VL_ICMS, 0)) AS icms, sum(coalesce(VL_IPI, 0)) AS ipi
                   FROM raw_icms_c190
                   WHERE (arquivo_id, pai_linha) IN (SELECT DISTINCT arquivo_id, pai_linha FROM raw_icms_c170)
                   GROUP BY ALL),
             c AS (SELECT coalesce(i.arquivo_id, a.arquivo_id) AS arquivo_id,
                          coalesce(i.pai_linha, a.pai_linha) AS doc_linha, coalesce(i.cfop, a.cfop) AS cfop,
                          coalesce(i.bc, 0) AS bc_icms_c170, coalesce(a.bc, 0) AS bc_icms_c190,
                          coalesce(i.icms, 0) AS icms_c170, coalesce(a.icms, 0) AS icms_c190,
                          coalesce(i.ipi, 0) AS ipi_c170, coalesce(a.ipi, 0) AS ipi_c190
                   FROM i FULL JOIN a ON i.arquivo_id = a.arquivo_id AND i.pai_linha = a.pai_linha AND i.cfop = a.cfop)
        SELECT d.raiz, d.cnpj_estab, d.mes, d.sentido, d.num_doc, d.chv_nfe, c.cfop,
               c.bc_icms_c170, c.bc_icms_c190, c.icms_c170, c.icms_c190, c.ipi_c170, c.ipi_c190,
               c.arquivo_id, c.doc_linha
        FROM c JOIN v_docs d ON d.arquivo_id = c.arquivo_id AND d.doc_linha = c.doc_linha
        WHERE NOT d.cancelado AND (abs(c.bc_icms_c170 - c.bc_icms_c190) > {tol}
              OR abs(c.icms_c170 - c.icms_c190) > {tol} OR abs(c.ipi_c170 - c.ipi_c190) > {tol})
        ORDER BY 1, 2, 3""").df()


# ---------------------------------------------------------------------------
# Cobertura: EFD ICMS/IPI de cada estabelecimento × EFD Contribuicoes da empresa, mes a mes
# ---------------------------------------------------------------------------
@dataclass
class Escrituracao:
    tipo: str                     # ICMS_IPI | CONTRIB
    cnpj: str
    ano: int
    mes: int
    uf: str = ""
    nome: str = ""
    origem: str = "banco"         # banco | pasta
    arquivo: str = ""
    estabs: list[tuple[str, str, str, str]] = field(default_factory=list)  # Contrib 0140: cnpj, uf, ie, nome

    @property
    def raiz(self) -> str:
        return self.cnpj[:8]


def _contribuinte_icms(ie: str | None) -> bool:
    return bool(ie and ie.strip() and not ie.strip().upper().startswith("ISENT"))


def escrituracoes_do_banco(con: duckdb.DuckDBPyConnection) -> list[Escrituracao]:
    arq = con.execute("""SELECT arquivo_id, tipo, cnpj, year(dt_ini), month(dt_ini), uf, nome, nome_arquivo
                         FROM arquivos WHERE ativo""").fetchall()
    est: dict[int, list] = {}
    for aid, cnpj, uf, ie, nome in con.execute(
            """SELECT e.arquivo_id, e.CNPJ, e.UF, e.IE, e.NOME FROM raw_contrib_0140 e
               JOIN arquivos a USING (arquivo_id) WHERE a.ativo""").fetchall():
        est.setdefault(aid, []).append((cnpj or "", uf or "", ie or "", nome or ""))
    return [Escrituracao(t, c, int(an), int(m), u or "", n or "", "banco", na, est.get(aid, []))
            for aid, t, c, an, m, u, n, na in arq]


def identificar_rapido(caminho: Path) -> Escrituracao:
    """Le so o registro 0000 (e, na EFD Contribuicoes, os 0140 do bloco 0) para saber tipo,
    estabelecimento/empresa e periodo, sem importar o arquivo."""
    from .parsers.base import detectar_encoding, identificar, ler_primeira_linha, separar_campos
    enc = detectar_encoding(caminho)
    ide = identificar(ler_primeira_linha(caminho, enc))
    e = Escrituracao(ide.tipo, ide.cnpj, ide.dt_ini.year, ide.dt_ini.month, ide.uf or "", ide.nome or "",
                     "pasta", caminho.name)
    if ide.tipo == "CONTRIB":
        with open(caminho, encoding=enc, errors="replace") as fh:
            for i, linha in enumerate(fh):
                if linha.startswith("|0140|"):
                    c = separar_campos(linha) or []
                    c += [""] * 9
                    e.estabs.append((c[3], c[4], c[5], c[2]))   # CNPJ, UF, IE, NOME
                elif linha.startswith("|0990|") or (i > 50 and linha[:2] in ("|A", "|C", "|D", "|F", "|M", "|1")):
                    break
    return e


def cobertura(escrituracoes: list[Escrituracao], so_amazonas: bool = True) -> pd.DataFrame:
    """Uma linha por empresa × estabelecimento × mes: tem EFD ICMS/IPI? tem EFD Contribuicoes?

    Estabelecimentos considerados: os que tem EFD ICMS/IPI e os do 0140 da EFD Contribuicoes com
    inscricao estadual (contribuintes do ICMS). so_amazonas=True limita ao AM (perimetro da analise).
    Meses considerados: do primeiro ao ultimo mes com qualquer escrituracao da empresa."""
    if not escrituracoes:
        return pd.DataFrame(columns=["raiz", "empresa", "cnpj_estab", "uf", "ano", "mes", "icms_ipi",
                                     "contribuicoes", "no_0140", "situacao", "o_que_fazer"])
    fis = {(e.cnpj, e.ano, e.mes): e for e in escrituracoes if e.tipo == "ICMS_IPI"}
    con_ = {(e.raiz, e.ano, e.mes): e for e in escrituracoes if e.tipo == "CONTRIB"}
    nomes: dict[str, str] = {}
    estab_uf: dict[str, str] = {}
    estabs_raiz: dict[str, set] = {}
    no_0140: set = set()
    meses_raiz: dict[str, set] = {}
    for e in escrituracoes:
        meses_raiz.setdefault(e.raiz, set()).add((e.ano, e.mes))
        if e.tipo == "CONTRIB":
            nomes.setdefault(e.raiz, e.nome)
            for cnpj, uf, ie, _ in e.estabs:
                no_0140.add((cnpj, e.ano, e.mes))
                if cnpj and _contribuinte_icms(ie):
                    estab_uf.setdefault(cnpj, uf)
                    estabs_raiz.setdefault(e.raiz, set()).add(cnpj)
        else:
            nomes.setdefault(e.raiz, e.nome)
            estab_uf[e.cnpj] = e.uf
            estabs_raiz.setdefault(e.raiz, set()).add(e.cnpj)
    linhas = []
    for raiz, meses in meses_raiz.items():
        a0, a1 = min(meses), max(meses)
        todos = [(a, m) for a in range(a0[0], a1[0] + 1) for m in range(1, 13) if a0 <= (a, m) <= a1]
        ests = estabs_raiz.get(raiz) or {raiz}
        for cnpj in sorted(ests):
            uf = estab_uf.get(cnpj, "")
            if so_amazonas and uf and uf != "AM":
                continue
            for a, m in todos:
                ti = (cnpj, a, m) in fis
                tc = (raiz, a, m) in con_
                n0140 = (cnpj, a, m) in no_0140
                if ti and tc:
                    sit, faz = "OK", ""
                elif tc:
                    sit = "Falta EFD ICMS/IPI"
                    faz = ("Importar a EFD ICMS/IPI do estabelecimento" if n0140 else
                           "Importar a EFD ICMS/IPI (estabelecimento não está no 0140 deste mês: conferir)")
                elif ti:
                    sit, faz = "Falta EFD Contribuições", "Importar a EFD Contribuições da empresa (matriz)"
                else:
                    sit, faz = "Faltam as duas", "Importar as duas EFDs do mês"
                if ti and tc and not n0140 and con_[(raiz, a, m)].estabs:
                    sit, faz = "OK (estabelecimento fora do 0140)", "Conferir o 0140 da EFD Contribuições"
                linhas.append({"raiz": raiz, "empresa": nomes.get(raiz, ""), "cnpj_estab": cnpj, "uf": uf,
                               "ano": a, "mes": m, "icms_ipi": ti, "contribuicoes": tc, "no_0140": n0140,
                               "situacao": sit, "o_que_fazer": faz})
    return pd.DataFrame(linhas)


def cobertura_banco(con: duckdb.DuckDBPyConnection, so_amazonas: bool = True) -> pd.DataFrame:
    return cobertura(escrituracoes_do_banco(con), so_amazonas)


def faltas(cob: pd.DataFrame) -> pd.DataFrame:
    return cob[~cob["situacao"].str.startswith("OK")] if not cob.empty else cob


def q17_cobertura(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Conciliacao: escrituracoes faltando (estabelecimentos do AM)."""
    f = faltas(cobertura_banco(con))
    return f.rename(columns={"cnpj_estab": "cnpj_estab"}) if not f.empty else f
