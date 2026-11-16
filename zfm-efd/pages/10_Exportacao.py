import datetime as _dt

import streamlit as st

from zfm import exportacao, ui

ctx = ui.contexto(
    "10. Exportação",
    "Para que serve: gerar um Excel com a diferença To Be − As Is por ano, empresa e tributo, a "
    "ponte, a composição saídas × entradas, o teste de absorção, a vantagem competitiva do IPI, a "
    "reconciliação R5 e a aba 'Premissas adotadas'. Usa os filtros da barra lateral. O que fazer: "
    "clique em 'Gerar Excel' e depois em 'Baixar'.",
    intragrupo=True,
)

if st.button("Gerar Excel", type="primary"):
    with ui.protegido("gerar o Excel"):
        with st.spinner("Gerando..."):
            st.session_state["excel"] = exportacao.gerar_excel(ctx.con, ctx.filtro, ctx.teses, ctx.intra)
if st.session_state.get("excel"):
    st.download_button("Baixar Excel", st.session_state["excel"],
                       file_name=f"zfm_as_is_to_be_{_dt.datetime.now():%Y%m%d_%H%M}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("O arquivo é salvo pelo navegador na pasta Downloads.")
