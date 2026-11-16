import plotly.express as px
import streamlit as st

from zfm import qualidade, ui

ctx = ui.contexto(
    "5. Saídas",
    "Para que serve: ver só as saídas — receita por empresa, mês, CFOP, destino e produto, já "
    "líquida das devoluções de venda. O que fazer: use os filtros; confira se produtos "
    "incentivados e destinos (ZFM, outros estados, exportação) estão coerentes.",
    intragrupo=True,
)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("montar a tela de saídas"):
    doc = con.execute(f"SELECT * FROM v_saidas_doc WHERE uf_estab = 'AM' AND {f.sql()}").df()
    it = con.execute(f"""SELECT * FROM v_base_operacoes WHERE sentido = 'saida' AND {f.sql()}""").df()
    if ctx.intra:
        doc = doc[~doc["eh_grupo"]]
        it = it[~it["eh_grupo"].fillna(False).astype(bool)]
    st.subheader("Filtros")
    doc = ui.filtros_tabela(doc, {"cfop": "CFOP", "categoria_cfop": "Categoria do CFOP", "uf": "UF de destino",
                                  "tipo_operacao": "Tipo de operação"}, "sai_doc")
    it = ui.filtros_tabela(it, {"cod_item": "Produto", "ncm_produto": "NCM", "incentivado": "Incentivado",
                                "natureza": "Natureza"}, "sai_it")
    if not doc.empty:
        sel_cfop = set(doc["cfop"].astype(str))
        it = it[it["cfop"].astype(str).isin(sel_cfop) | it["natureza"].eq("devolucao_venda")]
    rec = doc[doc["eh_receita"]] if not doc.empty else doc

    st.subheader("Receita por empresa e mês (EFD ICMS/IPI, C190, CFOPs de receita, valor bruto)")
    ui.tabela(ui.por_empresa(rec, ["mes"], "vl_opr", nomes))
    st.subheader("Por tipo de operação")
    t = rec.groupby(["tipo_operacao", "raiz"], as_index=False)["vl_opr"].sum() if not rec.empty else rec
    ui.tabela(ui.por_empresa(t, ["tipo_operacao"], "vl_opr", nomes))
    if not t.empty:
        visao = st.radio("Gráfico", ["Total", "Por empresa"], horizontal=True, key="g_saidas")
        t["empresa"] = t["raiz"].map(lambda r: nomes.get(r, r))
        st.plotly_chart(px.bar(t, x="tipo_operacao", y="vl_opr",
                               color="empresa" if visao == "Por empresa" else None,
                               labels={"vl_opr": "R$", "tipo_operacao": "Tipo de operação"}),
                        use_container_width=True)
    st.subheader("Por CFOP e UF de destino")
    ui.tabela(ui.por_empresa(doc, ["cfop", "categoria_cfop", "uf"], "vl_opr", nomes))

    st.subheader("Base de saídas por produto (EFD Contribuições, líquida de devoluções)")
    if not it.empty and it["rateado"].any():
        st.info("Parte das linhas usa rateio do destino (EFD Contribuições consolidada): o destino de "
                "cada produto foi distribuído pela proporção do C190 no mesmo mês e CFOP.")
    ui.tabela(ui.por_empresa(it, ["natureza", "cod_item", "ncm_produto", "incentivado"], "valor", nomes))
    st.subheader("Devoluções de venda (abatem a receita)")
    ui.tabela(ui.por_empresa(it[it.natureza == "devolucao_venda"], ["mes", "cod_item", "cfop"], "valor", nomes))
    st.subheader("Distribuição de CST")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("ICMS (C190)")
        ui.tabela(doc.groupby("cst_icms", as_index=False)["vl_opr"].sum() if not doc.empty else doc)
    with c2:
        st.markdown("PIS / COFINS / IPI (itens)")
        ui.tabela(it.groupby(["cst_pis", "aliq_pis", "cst_cofins", "aliq_cofins", "cst_ipi"],
                             dropna=False, as_index=False)["valor"].sum() if not it.empty else it,
                  moeda=["valor"])
    st.subheader("Saídas para destinatários na ZFM (base dos arts. 448/451)")
    ui.tabela(ui.por_empresa(rec[rec.tipo_operacao == "zfm_interna"] if not rec.empty else rec, ["mes"],
                             "vl_opr", nomes))
    st.subheader("Exportações (fora da análise; ficam na base sem débito)")
    ui.tabela(ui.por_empresa(rec[rec.tipo_operacao == "exportacao"] if not rec.empty else rec, ["mes"],
                             "vl_opr", nomes))
    with st.expander("Documentos de origem (arquivo e linha)"):
        if not doc.empty:
            ui.tabela(doc[["raiz", "cnpj_estab", "mes", "num_doc", "chv_nfe", "cfop", "cst_icms", "vl_opr",
                           "nome_part", "uf", "tipo_operacao", "arquivo_id", "linha_num"]],
                      moeda=["vl_opr"], altura=400)
            ui.baixar_csv(doc, "saidas_documentos")
    st.caption("Meses: " + ", ".join(qualidade.MESES[m - 1] for m in f.meses))
