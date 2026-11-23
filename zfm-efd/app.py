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
        P("telas/qualidade.py", title="Qualidade e conferências", icon=":material/fact_check:", url_path="qualidade"),
        P("telas/parametros.py", title="Cadastros", icon=":material/tune:", url_path="cadastros"),
    ],
    "Análise": [
        P("telas/operacoes.py", title="Operações", icon=":material/table_view:", url_path="operacoes"),
        P("telas/cenarios.py", title="Cenários ZFM", icon=":material/account_tree:", url_path="cenarios"),
        P("telas/resultado.py", title="Resultado As Is × To Be", icon=":material/trending_up:", url_path="resultado"),
        P("telas/simulador.py", title="Simulador individual", icon=":material/calculate:", url_path="simulador"),
    ],
    "Relatórios": [
        P("telas/exportacao.py", title="Exportação para Excel", icon=":material/download:", url_path="exportacao"),
    ],
}
st.navigation(paginas, expanded=True).run()
