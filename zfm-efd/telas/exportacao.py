import datetime as _dt

import streamlit as st

from zfm import exportacao, ui

ctx = ui.contexto(
    "Exportação para Excel",
    "Gera um Excel com uma aba por visão: matriz de cenários, As Is × To Be por cenário, IPI por produto, alertas, "
    "não classificados, diferença por tributo e empresa, ponte, absorção, carga As Is, R5, benefício informativo, "
    "conciliações e a aba 'Premissas'. Usa os filtros da barra lateral.", "Relatórios", intragrupo=True)

ui.secao("Conteúdo", "Empresas, período, estabelecimentos e a opção 'Com teses' da barra lateral valem para todas "
         "as abas. O arquivo é gerado neste computador e salvo pelo navegador na pasta Downloads.")
c1, c2 = st.columns([1, 3], vertical_alignment="center")
if c1.button("Gerar Excel", type="primary", icon=":material/table:", width="stretch"):
    with ui.protegido("gerar o Excel"):
        with st.spinner("Gerando o Excel (pode levar alguns minutos com bases grandes)..."):
            st.session_state["excel"] = exportacao.gerar_excel(ctx.con, ctx.filtro, ctx.teses, ctx.intra)
            st.session_state["excel_nome"] = f"zfm_as_is_to_be_{_dt.datetime.now():%Y%m%d_%H%M}.xlsx"
if st.session_state.get("excel"):
    c2.download_button("Baixar Excel", st.session_state["excel"], file_name=st.session_state["excel_nome"],
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       icon=":material/download:")
