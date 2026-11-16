import plotly.express as px
import streamlit as st

from zfm import ui

ctx = ui.contexto(
    "6. Entradas",
    "Para que serve: ver só as entradas — compras por região de origem (base dos créditos "
    "presumidos dos arts. 447 e 449), importações, fornecedores da ZFM, CSTs e devoluções de "
    "compra. O que fazer: confira a origem dos fornecedores (depende do município no 0150).",
    intragrupo=True,
)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("montar a tela de entradas"):
    e = con.execute(f"SELECT * FROM v_base_operacoes WHERE sentido = 'entrada' AND {f.sql()}").df()
    if ctx.intra:
        e = e[~e["eh_grupo"].fillna(False).astype(bool)]
    if e.empty:
        st.warning("Sem entradas para o filtro escolhido.")
        st.stop()
    regiao = {"importacao": "Importação", "zfm": "ZFM", "am_fora_zfm": "Amazonas fora da ZFM",
              "servicos": "Serviços tomados"}
    e["regiao_origem"] = [regiao.get(o) or ("Sul/Sudeste exceto ES" if s else "Norte, Nordeste, Centro-Oeste e ES")
                          for o, s in zip(e["origem"], e["sul_sudeste_exceto_es"].fillna(False))]
    st.subheader("Filtros")
    e = ui.filtros_tabela(e, {"regiao_origem": "Origem", "categoria_origem": "Finalidade",
                              "natureza": "Natureza", "uf_part": "UF do fornecedor", "cfop": "CFOP",
                              "cod_item": "Produto", "eh_grupo": "Empresa do grupo"}, "ent")
    st.subheader("Por região de origem")
    ui.tabela(ui.por_empresa(e, ["regiao_origem"], "valor", nomes))
    if not e.empty:
        g = e.groupby(["regiao_origem", "raiz"], as_index=False)["valor"].sum()
        visao = st.radio("Gráfico", ["Total", "Por empresa"], horizontal=True, key="g_ent")
        g["empresa"] = g["raiz"].map(lambda r: nomes.get(r, r))
        st.plotly_chart(px.bar(g, x="regiao_origem", y="valor",
                               color="empresa" if visao == "Por empresa" else None,
                               labels={"valor": "R$", "regiao_origem": "Origem"}), use_container_width=True)
    st.subheader("Por finalidade (CFOP de origem)")
    ui.tabela(ui.por_empresa(e, ["categoria_origem", "natureza"], "valor", nomes))
    st.caption("Uso e consumo e ativo ficam separados; transferências e remessas não geram crédito na "
               "simulação. Devoluções de compra têm valor negativo e abatem a compra de origem.")
    st.subheader("Fornecedores da ZFM (base do art. 449)")
    ui.tabela(ui.por_empresa(e[e.origem == "zfm"], ["cnpj_part", "categoria_origem"], "valor", nomes))
    st.subheader("Importações (CFOP 3xxx)")
    ui.tabela(ui.por_empresa(e[e.origem == "importacao"], ["mes"], "valor", nomes))
    st.subheader("Devoluções de compra")
    ui.tabela(ui.por_empresa(e[e.natureza == "devolucao_compra"], ["mes", "cfop", "categoria_origem"], "valor", nomes))
    st.subheader("CST nas entradas")
    ui.tabela(e.groupby(["cst_icms", "cst_ipi", "cst_pis", "cst_cofins"], dropna=False,
                        as_index=False)["valor"].sum(), moeda=["valor"])
    with st.expander("Registros de origem (arquivo e linha)"):
        ui.tabela(e[["raiz", "cnpj_estab", "mes", "chv_nfe", "cod_item", "cfop", "natureza", "valor",
                     "cnpj_part", "uf_part", "regiao_origem", "reg_origem", "arquivo_id", "linha_num"]],
                  moeda=["valor"], altura=400)
        ui.baixar_csv(e, "entradas")
