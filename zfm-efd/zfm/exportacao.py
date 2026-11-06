"""Exportacao para Excel (openpyxl) e CSV (';', UTF-8 com BOM) - SPEC 8, tela 9."""
from __future__ import annotations

import datetime as _dt
import io

import duckdb
import pandas as pd

from . import beneficio_atual as ba
from . import conciliacoes, params, qualidade, simulacao


def _por_empresa(df: pd.DataFrame, indice: list[str], valor: str, nomes: dict[str, str]) -> pd.DataFrame:
    """Colunas por empresa + Total."""
    if df.empty:
        return df
    p = df.pivot_table(index=indice, columns="raiz", values=valor, aggfunc="sum", fill_value=0.0)
    p.columns = [nomes.get(c, c) for c in p.columns]
    p["Total"] = p.sum(axis=1)
    return p.reset_index()


def gerar_excel(con: duckdb.DuckDBPyConnection, raizes: list[str] | None, com_teses: bool,
                eliminar_intragrupo: bool) -> bytes:
    emp = params.carregar("param_empresas")
    nomes = {r.raiz_cnpj: (r.nome_curto or r.razao_social or r.raiz_cnpj) for r in emp.itertuples()}

    def filtra(df: pd.DataFrame) -> pd.DataFrame:
        if raizes is None or df.empty or "raiz" not in df.columns:
            return df
        return df[df["raiz"].isin(raizes)]

    det = filtra(ba.calcular(con, com_teses=com_teses, eliminar_intragrupo=eliminar_intragrupo))
    anual, mensal = simulacao.simular(con, com_teses=com_teses, eliminar_intragrupo=eliminar_intragrupo)
    anual, mensal = filtra(anual), filtra(mensal)
    abas: dict[str, pd.DataFrame] = {}
    abas["Resumo"] = pd.DataFrame([
        ["Gerado em", f"{_dt.datetime.now():%d/%m/%Y %H:%M}"],
        ["Empresas", "todas (consolidado)" if raizes is None else ", ".join(nomes.get(r, r) for r in raizes)],
        ["Com teses", "sim" if com_teses else "não"],
        ["Eliminação de operações entre empresas do grupo", "sim" if eliminar_intragrupo else "não"],
    ], columns=["Item", "Valor"])
    if not det.empty:
        abas["Benefício atual"] = _por_empresa(det, ["tributo"], "beneficio", nomes)
        abas["Benefício por mês"] = _por_empresa(det, ["mes", "tributo"], "beneficio", nomes)
        abas["Benefício por produto"] = _por_empresa(det.fillna({"cod_item": "(não alocado)"}),
                                                     ["cod_item", "tributo"], "beneficio", nomes)
        abas["Benefício - registros"] = det
    abas["Premissas adotadas"] = params.resumo_premissas()
    if not anual.empty:
        cols = ["beneficio_hoje", "beneficio_cbs", "beneficio_ibs", "beneficio_icms", "beneficio_ipi",
                "beneficio_contrib_457", "beneficio_teses", "beneficio_pos", "delta"]
        long = anual.melt(id_vars=["cenario", "ano", "raiz"], value_vars=cols, var_name="medida")
        abas["Simulação"] = _por_empresa(long, ["cenario", "ano", "medida"], "value", nomes)
        se = anual.melt(id_vars=["cenario", "ano", "raiz"],
                        value_vars=["beneficio_saidas", "beneficio_entradas", "beneficio_pos"],
                        var_name="medida")
        abas["Simulação saídas x entradas"] = _por_empresa(se, ["cenario", "ano", "medida"], "value", nomes)
        abas["Simulação - detalhe"] = anual
        abas["Teste de absorção"] = mensal
    abas["Saídas por CFOP"] = filtra(con.execute("""
        SELECT raiz, mes, cfop, tipo_operacao, categoria_cfop, sum(vl_opr) AS valor_operacao,
               sum(vl_icms_c190) AS icms, sum(vl_ipi_c190) AS ipi
        FROM v_saidas_doc GROUP BY ALL ORDER BY ALL""").df())
    ed = filtra(ba.entradas_desoneradas(con))
    if not ed.empty:
        abas["Entradas desoneradas (info)"] = _por_empresa(
            ed, ["tributo", "cst", "situacao"], "valor_entradas", nomes)
    abas["Entradas por origem"] = filtra(con.execute("""
        SELECT raiz, mes, regiao_origem, categoria_cfop, sum(valor) AS valor
        FROM v_entradas_item GROUP BY ALL ORDER BY ALL""").df())
    abas["Apuração ICMS"] = filtra(con.execute("SELECT * EXCLUDE (linha_num) FROM v_apur_icms ORDER BY ALL").df())
    abas["Apuração IPI"] = filtra(con.execute("SELECT * EXCLUDE (linha_num) FROM v_apur_ipi ORDER BY ALL").df())
    abas["Apuração PIS-COFINS"] = filtra(con.execute("SELECT * FROM v_apur_pis_cofins ORDER BY ALL").df())
    abas["Completude Q1"] = filtra(qualidade.q1_completude(con))
    for k, (titulo, f) in conciliacoes.CHECAGENS.items():
        d = conciliacoes.filtrar(f(con), raizes)
        if not d.empty:
            abas[f"{k} divergências"] = d
    # Premissas: todos os parametros usados
    prem = []
    for nome, t in params.TABELAS.items():
        df = params.carregar(nome)
        prem.append(pd.DataFrame([[f"### {t.titulo} ({nome})"]], columns=["tabela"]))
        prem.append(df.astype(str))
    abas["Parâmetros (tabelas)"] = pd.concat(prem, ignore_index=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for nome, df in abas.items():
            df = df.copy()
            for c in df.columns:
                if str(df[c].dtype).startswith("decimal") or df[c].dtype == object:
                    try:
                        df[c] = pd.to_numeric(df[c]) if df[c].map(lambda v: hasattr(v, "as_tuple")).any() else df[c]
                    except (ValueError, TypeError):
                        pass
            df.to_excel(xw, sheet_name=nome[:31], index=False)
            ws = xw.sheets[nome[:31]]
            for col in ws.columns:
                largura = max(len(str(c.value or "")) for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, largura + 2), 60)
                for c in col[1:]:
                    if isinstance(c.value, float):
                        c.number_format = "#,##0.00"
    return buf.getvalue()


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")
