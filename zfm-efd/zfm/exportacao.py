"""Exportacao para Excel (openpyxl) e CSV (';', UTF-8 com BOM) - etapa 9."""
from __future__ import annotations

import datetime as _dt
import io

import duckdb
import pandas as pd

from . import as_is, beneficio_atual as ba
from . import conciliacoes, params, qualidade, simulacao
from .filtros import TODOS, Filtro


def _por_empresa(df: pd.DataFrame, indice: list[str], valor: str, nomes: dict[str, str]) -> pd.DataFrame:
    """Colunas por empresa + Total."""
    if df.empty:
        return df
    p = df.pivot_table(index=indice, columns="raiz", values=valor, aggfunc="sum", fill_value=0.0, sort=False,
                       observed=True)
    p.columns = [nomes.get(c, c) for c in p.columns]
    p["Total"] = p.sum(axis=1)
    return p.reset_index()


def gerar_excel(con: duckdb.DuckDBPyConnection, f: Filtro | list[str] | None = None, com_teses: bool = False,
                eliminar_intragrupo: bool = False) -> bytes:
    if f is None:
        f = TODOS
    elif not isinstance(f, Filtro):
        f = Filtro(raizes=tuple(f))
    emp = params.carregar("param_empresas")
    nomes = {r.raiz_cnpj: (r.nome_curto or r.razao_social or r.raiz_cnpj) for r in emp.itertuples()}

    def filtra(df: pd.DataFrame) -> pd.DataFrame:
        return conciliacoes.filtrar(df, f)

    anual, mensal = simulacao.simular(con, f, com_teses)
    abas: dict[str, pd.DataFrame] = {}
    abas["Resumo"] = pd.DataFrame([
        ["Gerado em", f"{_dt.datetime.now():%d/%m/%Y %H:%M}"],
        ["Empresas", "todas (consolidado)" if f.raizes is None else ", ".join(nomes.get(r, r) for r in f.raizes)],
        ["Estabelecimentos", "todos" if f.estabs is None else ", ".join(f.estabs)],
        ["Período (meses)", f"{f.mes_ini:02d} a {f.mes_fim:02d}"],
        ["Com teses", "sim" if com_teses else "não"],
        ["Sinal da diferença", "To Be − As Is: positivo = aumento de carga (perda); negativo = ganho"],
    ], columns=["Item", "Valor"])
    abas["Premissas adotadas"] = params.resumo_premissas()
    if not anual.empty:
        dif = simulacao.diferenca_por_tributo(anual)
        abas["Diferença por tributo"] = _por_empresa(dif, ["cenario", "ano", "tributo"], "diferenca", nomes)
        tot = anual[["cenario", "ano", "raiz", "as_is_total", "to_be_total", "diferenca_total",
                     "ajuste_reconciliacao_total", "to_be_total_teorico", "diferenca_total_teorica",
                     "perda_vantagem_ipi"]].copy()
        tot.insert(3, "empresa", tot["raiz"].map(lambda r: nomes.get(r, r)))
        abas["Diferença por empresa"] = tot.sort_values(["cenario", "ano", "diferenca_total"],
                                                        ascending=[True, True, False])
        pontes = []
        for (c, a), _ in anual.groupby(["cenario", "ano"], sort=False):
            p = simulacao.ponte(anual, c, a)
            p.insert(0, "ano", a)
            p.insert(0, "cenario", c)
            pontes.append(p)
        abas["Ponte As Is → To Be"] = pd.concat(pontes, ignore_index=True)
        comp = simulacao.composicao(anual, con, f)
        if not comp.empty:
            abas["Saídas x entradas"] = _por_empresa(comp, ["cenario", "ano", "regime", "tributo", "lado",
                                                            "componente"], "valor", nomes)
        abas["Vantagem competitiva IPI"] = _por_empresa(
            anual.melt(id_vars=["cenario", "ano", "raiz"],
                       value_vars=["ipi_conc_as_is", "ipi_conc_to_be", "perda_vantagem_ipi"], var_name="medida"),
            ["cenario", "ano", "medida"], "value", nomes)
        abas["Absorção (anual)"] = anual[["cenario", "ano", "raiz", "cp_cbs_gerado", "cp_cbs_usado",
                                          "cp_cbs_expirado", "cp_entrada_gerado", "cp_entrada_usado",
                                          "cp_entrada_expirado", "cp_ibs_450", "meses_saldo_credor"]]
        abas["Absorção (mensal)"] = mensal
        abas["Simulação - detalhe"] = anual
    asis = as_is.carga_anual(con, f, com_teses)
    if not asis.empty:
        abas["Carga As Is (anual)"] = _por_empresa(
            asis.melt(id_vars=["raiz", "tributo"], value_vars=["as_is", "as_is_base", "ajuste_reconciliacao",
                                                               "teses"], var_name="medida"),
            ["tributo", "medida"], "value", nomes)
        abas["Carga As Is (mensal)"] = as_is.carga_mensal(con, f)
    abas["R5 reconciliação"] = as_is.reconciliacao_r5(con, f)
    abas["Saldos credores finais"] = as_is.saldos_credores_finais(con, f)
    abas["Base de operações (resumo)"] = con.execute(f"""
        SELECT raiz, mes, sentido, natureza, categoria_origem, tipo_operacao, origem, incentivado,
               sum(valor) AS valor, sum(icms) AS icms, sum(ipi) AS ipi, sum(pis) AS pis, sum(cofins) AS cofins
        FROM v_base_operacoes WHERE {f.sql()} GROUP BY ALL ORDER BY ALL""").df()
    det = ba.calcular(con, com_teses=com_teses, eliminar_intragrupo=eliminar_intragrupo, f=f)
    if not det.empty:
        abas["Benefício ZFM (informativo)"] = _por_empresa(det, ["tributo"], "beneficio", nomes)
        abas["Benefício por produto (info)"] = _por_empresa(det.fillna({"cod_item": "(não alocado)"}),
                                                            ["cod_item", "tributo"], "beneficio", nomes)
    abas["Completude Q1"] = filtra(qualidade.q1_completude(con))
    for k, (titulo, func) in conciliacoes.CHECAGENS.items():
        d = filtra(func(con))
        if not d.empty:
            abas[f"{k} divergências"] = d
    prem = []
    for nome, t in params.TABELAS.items():
        df = params.carregar(nome)
        prem.append(pd.DataFrame([[f"### {t.titulo} ({nome})"]], columns=["tabela"]))
        prem.append(df.astype(str))
    abas["Parâmetros (tabelas)"] = pd.concat(prem, ignore_index=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for nome, df in abas.items():
            if df is None:
                continue
            nome_aba = nome[:31]
            df.to_excel(xw, sheet_name=nome_aba, index=False)
            ws = xw.sheets[nome_aba]
            for col in ws.columns:
                largura = max(len(str(c.value or "")) for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, largura + 2), 60)
                for c in col[1:]:
                    if isinstance(c.value, float):
                        c.number_format = "#,##0.00"
    return buf.getvalue()


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")
