import plotly.express as px
import streamlit as st

from zfm import qualidade, ui

ui.cabecalho(
    "5. Entradas",
    "Para que serve: ver as compras por região de origem (base dos créditos presumidos dos "
    "arts. 447 e 449), importações, fornecedores da ZFM e CSTs. O que fazer: confira se a origem "
    "dos fornecedores está correta (depende do município no cadastro 0150).",
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

with ui.protegido("montar a tela de entradas"):
    e = con.execute("SELECT * FROM v_entradas_item WHERE raiz IN (SELECT unnest(?))", [raizes]).df()
    if intra:
        e = e[~e["eh_grupo"]]
    meses = st.multiselect("Mês", sorted(e["mes"].unique()) if not e.empty else [],
                           format_func=lambda m: qualidade.MESES[m - 1])
    if meses:
        e = e[e.mes.isin(meses)]
    st.subheader("Por região de origem")
    ui.tabela(ui.por_empresa(e, ["regiao_origem"], "valor", nomes))
    if not e.empty:
        g = e.groupby(["regiao_origem", "raiz"], as_index=False)["valor"].sum()
        visao = st.radio("Gráfico", ["Total", "Por empresa"], horizontal=True, key="g_ent")
        g["empresa"] = g["raiz"].map(lambda r: nomes.get(r, r))
        st.plotly_chart(px.bar(g, x="regiao_origem", y="valor",
                               color="empresa" if visao == "Por empresa" else None,
                               labels={"valor": "R$", "regiao_origem": "Origem"}), use_container_width=True)
        uf = e.groupby("uf", as_index=False)["valor"].sum().sort_values("valor", ascending=False)
        st.markdown("Por UF de origem")
        ui.tabela(uf)
    st.subheader("Por finalidade (CFOP)")
    ui.tabela(ui.por_empresa(e, ["categoria_cfop"], "valor", nomes))
    st.caption("Uso e consumo e ativo imobilizado ficam separados; transferências, devoluções e "
               "remessas não geram crédito na simulação.")
    st.subheader("Fornecedores da ZFM (base do art. 449)")
    ui.tabela(e[e.origem == "zfm"].groupby(["raiz", "nome_part", "cnpj_part", "categoria_cfop"],
                                            as_index=False)["valor"].sum())
    st.subheader("Importações (CFOP 3xxx)")
    ui.tabela(ui.por_empresa(e[e.origem == "importacao"], ["mes"], "valor", nomes))
    st.subheader("CST nas entradas")
    ui.tabela(e.groupby(["cst_icms", "cst_ipi", "cst_pis", "cst_cofins"], dropna=False,
                        as_index=False)["valor"].sum(), moeda=["valor"])
    st.caption("Benefícios nas entradas (isenção, alíquota zero, suspensão) são informativos e não "
               "entram no total do benefício (premissa 'beneficio_entradas_no_total').")
    with st.expander("Registros de origem (arquivo e linha)"):
        ui.tabela(e[["raiz", "cnpj_estab", "mes", "chv_nfe", "cod_item", "cfop", "valor", "nome_part",
                     "uf", "regiao_origem", "reg_origem", "arquivo_id", "linha_num"]],
                  moeda=["valor"], altura=400)
