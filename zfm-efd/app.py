"""Entrada do programa (Streamlit). Abra pelo iniciar.bat."""
import streamlit as st

st.set_page_config(page_title="ZFM x Reforma Tributária", page_icon="📊", layout="wide")

paginas = [
    st.Page("pages/0_Inicio.py", title="Início", icon="🏠", default=True),
    st.Page("pages/1_Carga_de_arquivos.py", title="1. Carga de arquivos", icon="📂"),
    st.Page("pages/2_Perimetro_e_qualidade.py", title="2. Perímetro e qualidade", icon="✅"),
]
st.navigation(paginas).run()
