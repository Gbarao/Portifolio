import streamlit as st

from zfm import ui

ui.cabecalho(
    "Análise ZFM × Reforma Tributária",
    "Este programa lê as EFD ICMS/IPI e EFD Contribuições das empresas do grupo no Amazonas, "
    "confere os arquivos, calcula o benefício atual da Zona Franca e simula o benefício depois "
    "da Reforma Tributária. Tudo roda só neste computador: nenhum dado sai daqui.",
)
con = ui.conexao()
ui.seletor_empresas(con)

st.subheader("Como usar")
st.markdown(
    """
1. **Carga de arquivos** – informe a pasta onde estão as EFDs (.txt) e clique em *Carregar*.
2. **Perímetro e qualidade** – confira se há os dois arquivos de cada mês para cada
   estabelecimento e se os arquivos estão íntegros.
3. *(próximas versões)* Parâmetros, Saídas, Entradas, Apurações, Benefício atual,
   Simulação e Exportação para o Excel.
"""
)

if con is not None:
    with ui.protegido("ler o resumo do banco"):
        n = con.execute(
            "SELECT count(*) FILTER (WHERE ativo), count(DISTINCT raiz) FILTER (WHERE ativo) FROM arquivos"
        ).fetchall()[0]
        c1, c2 = st.columns(2)
        c1.metric("Arquivos em uso", f"{n[0]}")
        c2.metric("Empresas (raiz do CNPJ)", f"{n[1]}")

st.caption("Versão em construção: Fase 1 (leitura das EFDs e checagens Q1 e Q2).")
