import plotly.express as px
import streamlit as st

from zfm import qualidade, ui

ui.cabecalho(
    "4. Saídas",
    "Para que serve: ver a receita de saídas por empresa, mês, CFOP, destino e produto. "
    "O que fazer: use os filtros para localizar operações; confira se produtos incentivados e "
    "destinos (ZFM, outros estados, exportação) estão coerentes.",
)
con = ui.conexao()
sel = ui.seletor_empresas(con)
if con is None:
    st.stop()
if not ui.preparar(con):
    ui.aviso_sem_dados()
    st.stop()
_, intra = ui.filtros_globais()
raizes = ui.raizes_analise(con, sel)
ui.exigir_empresas(raizes)
nomes = ui.nomes_empresas()

with ui.protegido("montar a tela de saídas"):
    doc = con.execute("SELECT * FROM v_saidas_doc WHERE raiz IN (SELECT unnest(?))", [raizes]).df()
    it = con.execute("""SELECT s.*, coalesce(p.incentivado, FALSE) AS incentivado, p.tipo_bem
                        FROM v_saidas_dest s LEFT JOIN param_produtos p
                          ON p.raiz_cnpj = s.raiz AND p.cod_item = s.cod_item
                        WHERE s.raiz IN (SELECT unnest(?)) AND s.estab_no_am""", [raizes]).df()
    if intra:
        doc = doc[~doc["eh_grupo"]]
        it = it[~it["eh_grupo"].fillna(False).astype(bool)]
    f1, f2, f3, f4 = st.columns(4)
    meses = f1.multiselect("Mês", sorted(doc["mes"].unique()) if not doc.empty else [],
                           format_func=lambda m: qualidade.MESES[m - 1])
    cfops = f2.multiselect("CFOP", sorted(doc["cfop"].dropna().unique()) if not doc.empty else [])
    ufs = f3.multiselect("UF de destino", sorted(doc["uf"].dropna().unique()) if not doc.empty else [])
    prods = f4.multiselect("Produto", sorted(it["cod_item"].dropna().unique()) if not it.empty else [])
    if meses:
        doc, it = doc[doc.mes.isin(meses)], it[it.mes.isin(meses)]
    if cfops:
        doc, it = doc[doc.cfop.isin(cfops)], it[it.cfop.isin(cfops)]
    if ufs:
        doc, it = doc[doc.uf.isin(ufs)], it[it.uf_dest.isin(ufs)]
    if prods:
        it = it[it.cod_item.isin(prods)]
    rec = doc[doc["eh_receita"]]

    st.subheader("Receita por empresa e mês (EFD ICMS/IPI, C190, CFOPs de receita)")
    ui.tabela(ui.por_empresa(rec, ["mes"], "vl_opr", nomes))
    st.subheader("Por tipo de operação")
    t = rec.groupby(["tipo_operacao", "raiz"], as_index=False)["vl_opr"].sum()
    ui.tabela(ui.por_empresa(t, ["tipo_operacao"], "vl_opr", nomes))
    if not t.empty:
        visao = st.radio("Gráfico", ["Total", "Por empresa"], horizontal=True, key="g_saidas")
        t["empresa"] = t["raiz"].map(lambda r: nomes.get(r, r))
        fig = px.bar(t, x="tipo_operacao", y="vl_opr", color="empresa" if visao == "Por empresa" else None,
                     labels={"vl_opr": "R$", "tipo_operacao": "Tipo de operação"})
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Por CFOP e UF de destino")
    ui.tabela(ui.por_empresa(doc, ["cfop", "categoria_cfop", "uf"], "vl_opr", nomes))

    st.subheader("Receita por produto (EFD Contribuições)")
    if it["rateado"].any() if not it.empty else False:
        st.info("Parte das linhas usa rateio do destino (EFD Contribuições consolidada, C180/C181): "
                "o destino de cada produto foi distribuído pela proporção do C190 no mesmo mês e CFOP.")
    ui.tabela(ui.por_empresa(it, ["cod_item", "ncm", "incentivado", "tipo_bem"], "receita_r", nomes))
    st.subheader("Incentivado × não incentivado")
    ui.tabela(ui.por_empresa(it, ["incentivado", "categoria_cfop"], "receita_r", nomes))
    st.subheader("Distribuição de CST")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("ICMS (C190)")
        ui.tabela(doc.groupby("cst_icms", as_index=False)["vl_opr"].sum())
    with c2:
        st.markdown("PIS / COFINS / IPI (itens)")
        ui.tabela(it.groupby(["cst_pis", "aliq_pis", "cst_cofins", "aliq_cofins", "cst_ipi"],
                             dropna=False, as_index=False)["receita_r"].sum(),
                  moeda=["receita_r"])
    st.subheader("Saídas para destinatários na ZFM (base dos arts. 448/451)")
    ui.tabela(ui.por_empresa(doc[doc.tipo_operacao == "zfm_interna"], ["mes"], "vl_opr", nomes))
    st.subheader("Exportações (CFOP 7xxx)")
    ui.tabela(ui.por_empresa(doc[doc.tipo_operacao == "exportacao"], ["mes"], "vl_opr", nomes))
    with st.expander("Registros de origem (arquivo e linha)"):
        ui.tabela(doc[["raiz", "cnpj_estab", "mes", "num_doc", "chv_nfe", "cfop", "cst_icms", "vl_opr",
                       "nome_part", "uf", "tipo_operacao", "arquivo_id", "linha_num"]],
                  moeda=["vl_opr"], altura=400)
