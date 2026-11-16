"""Entrada do programa (Streamlit). Abra pelo iniciar.bat."""
import streamlit as st

st.set_page_config(page_title="ZFM x Reforma Tributária", page_icon="📊", layout="wide")

paginas = [
    st.Page("pages/0_Inicio.py", title="Início", icon="🏠", default=True),
    st.Page("pages/1_Carga_de_arquivos.py", title="1. Carga de arquivos", icon="📂"),
    st.Page("pages/2_Perimetro_e_qualidade.py", title="2. Perímetro e qualidade", icon="✅"),
    st.Page("pages/3_Parametros.py", title="3. Parâmetros e premissas", icon="⚙️"),
    st.Page("pages/4_Base_de_operacoes.py", title="4. Base de operações", icon="🗂️"),
    st.Page("pages/5_Saidas.py", title="5. Saídas", icon="📤"),
    st.Page("pages/6_Entradas.py", title="6. Entradas", icon="📥"),
    st.Page("pages/7_Carga_As_Is.py", title="7. Carga As Is (apuração)", icon="🧾"),
    st.Page("pages/8_To_Be_e_diferenca.py", title="8. To Be e diferença", icon="📈"),
    st.Page("pages/9_Beneficio_informativo.py", title="9. Benefício ZFM (informativo)", icon="💰"),
    st.Page("pages/10_Exportacao.py", title="10. Exportação", icon="📊"),
]
st.navigation(paginas).run()
