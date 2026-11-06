from pathlib import Path

import pandas as pd
import streamlit as st

from zfm import qualidade, ui
from zfm.config import pasta_dados
from zfm.parsers import ErroEFD, carregar_arquivo, listar_txt

ui.cabecalho(
    "1. Carga de arquivos",
    "Para que serve: ler as EFDs (.txt) para o banco local do programa. "
    "O que fazer: cole abaixo o caminho da pasta onde estão as EFDs e clique em 'Carregar arquivos'. "
    "O programa lê todos os .txt da pasta (e das subpastas) e reconhece sozinho se é EFD ICMS/IPI "
    "ou EFD Contribuições.",
)
con = ui.conexao()
ui.seletor_empresas(con)
if con is None:
    st.stop()

with st.expander("Como copiar o caminho da pasta no Windows Explorer"):
    st.markdown(
        """
1. Abra a pasta das EFDs no Windows Explorer.
2. Clique uma vez na **barra de endereço** (no alto da janela, onde aparece o nome da pasta).
3. O caminho fica selecionado (por exemplo `C:\\Users\\voce\\Documents\\EFDs`). Aperte **Ctrl+C**.
4. Volte aqui, clique no campo abaixo e aperte **Ctrl+V**.
"""
    )

arq_ultima = pasta_dados() / "ultima_pasta.txt"
ultima = arq_ultima.read_text(encoding="utf-8") if arq_ultima.exists() else ""
pasta = st.text_input("Pasta das EFDs", value=ultima, placeholder=r"C:\Users\voce\Documents\EFDs")

if st.button("Carregar arquivos", type="primary", disabled=not pasta.strip()):
    try:
        arquivos = listar_txt(pasta)
    except ErroEFD as e:
        st.error(str(e))
        arquivos = []
    if arquivos:
        arq_ultima.write_text(pasta.strip().strip('"'), encoding="utf-8")
        barra = st.progress(0.0, text="Iniciando...")
        resultados = []
        n = len(arquivos)
        for i, p in enumerate(arquivos):
            def prog(frac: float, txt: str, i=i) -> None:
                barra.progress(min((i + frac) / n, 1.0), text=f"Arquivo {i + 1} de {n} – {txt}")
            r = carregar_arquivo(con, p, progresso=prog)
            resultados.append(r)
        barra.progress(1.0, text="Concluído")
        sit = {"carregado": "Carregado", "duplicado": "Já existia", "erro": "Não carregado"}
        tab = pd.DataFrame([{"Arquivo": r.nome_arquivo, "Resultado": sit[r.situacao],
                             "Mensagem": r.mensagem} for r in resultados])
        ok = sum(r.situacao == "carregado" for r in resultados)
        erros = [r for r in resultados if r.situacao == "erro"]
        st.success(f"{ok} arquivo(s) carregado(s) de {n}.")
        if erros:
            st.error(f"{len(erros)} arquivo(s) não foram carregados. Veja a coluna 'Mensagem'.")
        st.dataframe(tab, hide_index=True, use_container_width=True)
        avisos = [(r.nome_arquivo, a) for r in resultados for a in r.avisos]
        if avisos:
            st.warning("Alguns arquivos têm avisos de leitura (o arquivo foi carregado, mas confira):")
            st.dataframe(pd.DataFrame(avisos, columns=["Arquivo", "Aviso"]), hide_index=True,
                         use_container_width=True)

st.subheader("Arquivos no banco")
with ui.protegido("listar os arquivos carregados"):
    tab = qualidade.arquivos_carregados(con)
    if tab.empty:
        st.caption("Nenhum arquivo carregado ainda.")
    else:
        tab = tab.rename(columns={
            "arquivo_id": "Nº", "nome_arquivo": "Arquivo", "tipo": "Tipo", "cnpj": "CNPJ",
            "ie": "IE", "uf": "UF", "nome": "Razão social", "periodo": "Período",
            "versao_layout": "Versão do leiaute", "retificadora": "Retificadora",
            "situacao": "Situação", "qtd_linhas": "Linhas", "carregado_em": "Carregado em"})
        st.dataframe(tab, hide_index=True, use_container_width=True)
        st.caption("'Substituído' = havia outra versão do mesmo CNPJ/IE/período; só a mais recente "
                   "(retificadora) é usada nos cálculos.")

with st.expander("Apagar todos os dados carregados"):
    st.write("Remove do banco local todos os arquivos já lidos (os .txt originais não são apagados).")
    confirma = st.checkbox("Confirmo que quero apagar os dados carregados")
    if st.button("Apagar dados", disabled=not confirma):
        with ui.protegido("apagar os dados"):
            from zfm import db
            db.apagar_dados(con)
            st.success("Dados apagados.")
            st.rerun()
