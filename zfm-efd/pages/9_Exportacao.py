import datetime as _dt

import streamlit as st

from zfm import exportacao, ui

ui.cabecalho(
    "9. Exportação",
    "Para que serve: gerar um arquivo Excel com os números da tela para as empresas selecionadas "
    "(uma coluna por empresa e uma de total), com a aba 'Premissas' listando todos os parâmetros "
    "usados. O que fazer: clique em 'Gerar Excel' e depois em 'Baixar'.",
)
con = ui.conexao()
sel = ui.seletor_empresas(con)
if con is None:
    st.stop()
if not ui.preparar(con):
    ui.aviso_sem_dados()
    st.stop()
teses, intra = ui.filtros_globais()
raizes = ui.raizes_analise(con, sel)
ui.exigir_empresas(raizes)

if st.button("Gerar Excel", type="primary"):
    with ui.protegido("gerar o Excel"):
        with st.spinner("Gerando..."):
            st.session_state["excel"] = exportacao.gerar_excel(con, raizes, teses, intra)
if st.session_state.get("excel"):
    st.download_button("Baixar Excel", st.session_state["excel"],
                       file_name=f"zfm_reforma_{_dt.datetime.now():%Y%m%d_%H%M}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("O arquivo é salvo pelo navegador na pasta Downloads.")
