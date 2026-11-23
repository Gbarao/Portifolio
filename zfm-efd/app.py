"""Entrada do programa (Streamlit). Abra pelo iniciar.bat."""
import streamlit as st

from zfm import ui

st.set_page_config(page_title="ZFM × Reforma Tributária", page_icon=":material/analytics:", layout="wide",
                   initial_sidebar_state="expanded")
ui.estilo()

P = st.Page
paginas = {
    "Visão geral": [
        P("telas/painel.py", title="Painel", icon=":material/dashboard:", default=True, url_path="painel"),
    ],
    "Dados": [
        P("telas/importacao.py", title="Importação das EFDs", icon=":material/upload_file:", url_path="importacao"),
        P("telas/qualidade.py", title="Qualidade e reconciliação", icon=":material/fact_check:",
          url_path="qualidade"),
        P("telas/parametros.py", title="Parâmetros e premissas", icon=":material/tune:", url_path="parametros"),
    ],
    "Operações": [
        P("telas/base_operacoes.py", title="Base de operações", icon=":material/table_view:", url_path="base"),
        P("telas/saidas.py", title="Saídas", icon=":material/north_east:", url_path="saidas"),
        P("telas/entradas.py", title="Entradas", icon=":material/south_west:", url_path="entradas"),
    ],
    "Análise": [
        P("telas/cenarios.py", title="Cenários ZFM (C1–C6)", icon=":material/account_tree:", url_path="cenarios"),
        P("telas/simulador.py", title="Simulador individual", icon=":material/calculate:", url_path="simulador"),
        P("telas/metodologia.py", title="Metodologia e cruzamentos", icon=":material/menu_book:",
          url_path="metodologia"),
        P("telas/carga_as_is.py", title="Carga As Is", icon=":material/receipt_long:", url_path="as-is"),
        P("telas/to_be.py", title="To Be e diferença", icon=":material/trending_up:", url_path="to-be"),
        P("telas/beneficio.py", title="Benefício ZFM (informativo)", icon=":material/savings:",
          url_path="beneficio"),
    ],
    "Relatórios": [
        P("telas/exportacao.py", title="Exportação para Excel", icon=":material/download:", url_path="exportacao"),
    ],
}
st.navigation(paginas, expanded=True).run()
