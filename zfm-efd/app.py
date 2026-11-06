"""Entrada do programa (Streamlit). Abra pelo iniciar.bat."""
import streamlit as st

st.set_page_config(page_title="ZFM x Reforma Tributária", page_icon="📊", layout="wide")

paginas = [
    st.Page("pages/0_Inicio.py", title="Início", icon="🏠", default=True),
    st.Page("pages/1_Carga_de_arquivos.py", title="1. Carga de arquivos", icon="📂"),
    st.Page("pages/2_Perimetro_e_qualidade.py", title="2. Perímetro e qualidade", icon="✅"),
    st.Page("pages/3_Parametros.py", title="3. Parâmetros", icon="⚙️"),
    st.Page("pages/4_Saidas.py", title="4. Saídas", icon="📤"),
    st.Page("pages/5_Entradas.py", title="5. Entradas", icon="📥"),
    st.Page("pages/6_Apuracoes.py", title="6. Apurações", icon="🧾"),
    st.Page("pages/7_Beneficio_atual.py", title="7. Benefício atual", icon="💰"),
    st.Page("pages/8_Simulacao.py", title="8. Simulação e cenários", icon="📈"),
    st.Page("pages/9_Exportacao.py", title="9. Exportação", icon="📊"),
]
st.navigation(paginas).run()
