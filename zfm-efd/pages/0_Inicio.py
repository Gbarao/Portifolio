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
1. **Carga de arquivos** – informe a pasta das EFDs (.txt) e clique em *Carregar*.
2. **Perímetro e qualidade** – completude, integridade e conciliações R1 a R5 (a base de
   operações precisa explicar a apuração antes de simular).
3. **Parâmetros e premissas** – clique em *Preencher a partir das EFDs*; revise produtos
   (alíquota TIPI), códigos de ajuste do ICMS e alíquotas de CBS/IBS por cenário.
4. **Base de operações, Saídas, Entradas** – operações normalizadas, com filtros.
5. **Carga As Is** – carga atual lida da apuração (sem recálculo).
6. **To Be e diferença** – carga 2027–2033 e diferença To Be − As Is
   (positivo = perda), ponte por tributo, ranking, absorção e vantagem competitiva do IPI.
7. **Benefício ZFM (informativo)** e **Exportação** para o Excel.
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

st.caption("Versão: análise As Is (apuração) × To Be (2027–2033).")
