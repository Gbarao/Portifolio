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
3. **Parâmetros** – clique em *Preencher a partir das EFDs* e revise: produtos incentivados
   e alíquota TIPI, classificação dos códigos de ajuste do ICMS, alíquotas de CBS/IBS por cenário.
4. **Saídas, Entradas, Apurações** – confira as operações e as apurações.
5. **Benefício atual** – benefício da ZFM hoje, por tributo, empresa, produto e mês.
6. **Simulação e cenários** – benefício pós-reforma, Δ por empresa e teste de absorção.
7. **Exportação** – Excel com os números e as premissas.
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

st.caption("Versão: Fases 0 a 7.")
