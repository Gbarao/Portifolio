"""Seção 'saidas' (antes uma tela própria). render(ctx) desenha o conteúdo dentro da tela que a chama."""
import plotly.express as px
import streamlit as st
from zfm import ui


def render(ctx):
    con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

    with ui.protegido("montar a tela de saídas"):
        intra = " AND NOT coalesce(eh_grupo, false)" if ctx.intra else ""
        od = f"uf_estab = 'AM' AND {f.sql()}{intra}"
        oi = f"sentido = 'saida' AND {f.sql()}{intra}"
        with st.expander("Filtros", icon=":material/filter_alt:"):
            fd = ui.filtros_sql(con, "v_saidas_doc", {"cfop": "CFOP", "categoria_cfop": "Categoria do CFOP",
                                                      "uf": "UF de destino", "tipo_operacao": "Tipo de operação"},
                                "sai_doc", od)
            fi = ui.filtros_sql(con, "v_base_operacoes", {"cod_item": "Produto", "ncm_produto": "NCM",
                                                          "incentivado": "Incentivado", "natureza": "Natureza"},
                                "sai_it", oi)
        od, oi = f"{od} AND {fd}", f"{oi} AND {fi}"
        rec = f"{od} AND eh_receita"
        k = con.execute(f"""SELECT coalesce(sum(vl_opr) FILTER (WHERE eh_receita), 0),
                                   coalesce(sum(vl_opr) FILTER (WHERE eh_receita AND tipo_operacao = 'zfm_interna'), 0),
                                   coalesce(sum(vl_opr) FILTER (WHERE eh_receita AND tipo_operacao = 'exportacao'), 0),
                                   count(DISTINCT coalesce(chv_nfe, CAST(arquivo_id AS VARCHAR) || '-' || CAST(doc_linha AS VARCHAR)))
                            FROM v_saidas_doc WHERE {od}""").fetchall()[0]
        dev = con.execute(f"SELECT coalesce(sum(valor), 0) FROM v_base_operacoes WHERE {oi} AND "
                          "natureza = 'devolucao_venda'").fetchall()[0][0]
        ui.cartoes({"Receita bruta (C190)": k[0], "Para a ZFM": k[1], "Exportação": k[2],
                    "Devoluções de venda": dev, "Documentos": ui.formatar_num(k[3])})

        t1, t2, t3, t4 = st.tabs(["Receita e destino", "Produtos", "CST", "Documentos"])
        with t1:
            ui.secao("Receita por mês", "EFD ICMS/IPI (C190), CFOPs de receita, valor bruto.")
            ui.tabela(ui.por_empresa(con.execute(f"SELECT mes, raiz, sum(vl_opr) AS vl_opr FROM v_saidas_doc "
                                                 f"WHERE {rec} GROUP BY ALL ORDER BY 1").df(), ["mes"], "vl_opr", nomes))
            ui.secao("Por tipo de operação")
            t = con.execute(f"SELECT tipo_operacao, raiz, sum(vl_opr) AS vl_opr FROM v_saidas_doc WHERE {rec} "
                            "GROUP BY ALL").df()
            if not t.empty:
                c1, c2 = st.columns([1.2, 1])
                with c1:
                    ui.tabela(ui.por_empresa(t, ["tipo_operacao"], "vl_opr", nomes))
                with c2:
                    g = t.groupby("tipo_operacao", as_index=False)["vl_opr"].sum().sort_values("vl_opr")
                    ui.grafico(px.bar(g, x="vl_opr", y="tipo_operacao", orientation="h",
                                      labels={"vl_opr": "R$", "tipo_operacao": ""}), 300)
            ui.secao("Por CFOP e UF de destino")
            ui.tabela(ui.por_empresa(con.execute(f"""SELECT cfop, categoria_cfop, uf, raiz, sum(vl_opr) AS vl_opr
                      FROM v_saidas_doc WHERE {od} GROUP BY ALL ORDER BY 1, 3""").df(),
                                     ["cfop", "categoria_cfop", "uf"], "vl_opr", nomes))
        with t2:
            ui.secao("Base de saídas por produto", "EFD Contribuições, líquida de devoluções.")
            ra = con.execute(f"SELECT bool_or(rateado) FROM v_base_operacoes WHERE {oi}").fetchall()[0][0]
            if ra:
                st.info("Parte das linhas usa rateio do destino (EFD Contribuições consolidada): o destino de cada "
                        "produto foi distribuído pela proporção do C190 no mesmo mês e CFOP.", icon=":material/info:")
            ui.tabela(ui.por_empresa(con.execute(f"""SELECT natureza, cod_item, ncm_produto, incentivado, raiz,
                      sum(valor) AS valor FROM v_base_operacoes WHERE {oi} GROUP BY ALL ORDER BY 1, 2""").df(),
                                     ["natureza", "cod_item", "ncm_produto", "incentivado"], "valor", nomes))
            ui.secao("Devoluções de venda (abatem a receita)")
            ui.tabela(ui.por_empresa(con.execute(f"""SELECT mes, cod_item, cfop, raiz, sum(valor) AS valor
                      FROM v_base_operacoes WHERE {oi} AND natureza = 'devolucao_venda' GROUP BY ALL ORDER BY 1""").df(),
                                     ["mes", "cod_item", "cfop"], "valor", nomes))
        with t3:
            c1, c2 = st.columns(2)
            with c1:
                ui.secao("ICMS (C190)")
                ui.tabela(con.execute(f"SELECT cst_icms, sum(vl_opr) AS vl_opr FROM v_saidas_doc WHERE {od} "
                                      "GROUP BY ALL ORDER BY 1").df())
            with c2:
                ui.secao("PIS / COFINS / IPI (itens)")
                ui.tabela(con.execute(f"""SELECT cst_pis, aliq_pis, cst_cofins, aliq_cofins, cst_ipi, sum(valor) AS valor
                          FROM v_base_operacoes WHERE {oi} GROUP BY ALL ORDER BY 1""").df(), moeda=["valor"])
        with t4:
            n = con.execute(f"SELECT count(*) FROM v_saidas_doc WHERE {od}").fetchall()[0][0]
            docs = con.execute(f"""SELECT raiz, cnpj_estab, mes, num_doc, chv_nfe, cfop, cst_icms, vl_opr, nome_part, uf,
                                          tipo_operacao, arquivo_id, linha_num
                                   FROM v_saidas_doc WHERE {od} ORDER BY vl_opr DESC LIMIT 3000""").df()
            st.caption(f"Maiores {ui.formatar_num(len(docs))} de {ui.formatar_num(n)} linhas (por valor).")
            ui.tabela(docs, moeda=["vl_opr"], altura=440)
            ui.baixar_csv(docs, "saidas_documentos")
