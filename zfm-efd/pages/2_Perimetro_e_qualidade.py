import streamlit as st

from zfm import qualidade, ui

ui.cabecalho(
    "2. Perímetro e qualidade",
    "Para que serve: conferir se os arquivos estão completos e íntegros antes de qualquer cálculo. "
    "O que fazer: verifique se a matriz está toda verde. Vermelho indica arquivo faltando: "
    "carregue o arquivo que falta na tela 'Carga de arquivos'.",
)
con = ui.conexao()
selecao = ui.seletor_empresas(con)
if con is None:
    st.stop()

CORES = {
    qualidade.OK: "background-color: #C8E6C9; color: #1B5E20",
    qualidade.FALTA_ICMS: "background-color: #FFCDD2; color: #B71C1C",
    qualidade.FALTA_CONTRIB: "background-color: #FFCDD2; color: #B71C1C",
    qualidade.FALTAM_AMBAS: "background-color: #EF9A9A; color: #B71C1C",
}

st.subheader("Q1 – Completude: os dois arquivos existem em todos os meses?")
with ui.protegido("montar a matriz de completude"):
    ano, mes_fim = qualidade.periodo_padrao(con)
    if mes_fim == 0:
        st.caption("Nenhum arquivo de 2026 carregado ainda.")
    else:
        mes_fim = st.select_slider("Último mês do período (2026 acumulado no ano)",
                                   options=list(range(1, 13)), value=mes_fim,
                                   format_func=lambda m: qualidade.MESES[m - 1])
        m = qualidade.q1_completude(con, ano, mes_fim)
        if selecao is not None:
            m = m[m["raiz"].isin(selecao)]
        meses = qualidade.MESES[:mes_fim]
        faltas = int((m[meses] != qualidade.OK).sum().sum()) if not m.empty else 0
        if faltas:
            st.error(f"{faltas} combinação(ões) estabelecimento × mês com arquivo faltando.")
        else:
            st.success("Todos os estabelecimentos do Amazonas têm as duas EFDs em todos os meses.")
        vis = m.rename(columns={"raiz": "Raiz CNPJ", "cnpj": "CNPJ", "ie": "IE", "nome": "Razão social"})
        st.dataframe(vis.style.map(lambda v: CORES.get(v, ""), subset=meses),
                     hide_index=True, use_container_width=True)
        st.caption("A EFD Contribuições é entregue pela matriz (uma por empresa); por isso ela é "
                   "procurada pela raiz do CNPJ. Estabelecimentos fora do Amazonas ficam fora.")

st.subheader("Q2 – Integridade: as contagens do bloco 9 batem com o que foi lido?")
with ui.protegido("verificar a integridade"):
    q2 = qualidade.q2_integridade(con)
    if selecao is not None and not q2.empty:
        q2 = q2[q2["cnpj"].str[:8].isin(selecao)]
    if q2.empty:
        st.success("Nenhuma divergência: os totais dos registros 9900 e 9999 conferem.")
    else:
        st.error(f"{len(q2)} divergência(s). O arquivo pode estar incompleto ou alterado.")
        st.dataframe(q2.rename(columns={
            "arquivo_id": "Nº", "nome_arquivo": "Arquivo", "tipo": "Tipo", "cnpj": "CNPJ",
            "dt_ini": "Início", "registro": "Registro", "qtd_lida": "Qtd. lida",
            "qtd_informada_9900": "Qtd. informada", "problema": "Problema"}),
            hide_index=True, use_container_width=True)

st.subheader("Avisos de leitura")
with ui.protegido("listar os avisos"):
    av = qualidade.avisos_carga(con)
    if av.empty:
        st.caption("Nenhum aviso.")
    else:
        st.dataframe(av, hide_index=True, use_container_width=True)

st.caption("As checagens Q3 a Q11 (conciliações entre documentos, apurações e as duas EFDs) "
           "entram na Fase 3.")
