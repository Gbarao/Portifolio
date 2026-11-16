import time

import pandas as pd
import streamlit as st

from zfm import db, qualidade, ui
from zfm.config import pasta_dados
from zfm.parsers import ErroEFD, listar_txt

ui.marca()
con = ui.conexao()
if con is None:
    st.stop()
ui.seletor_empresas(con)
ui.cabecalho("Importação das EFDs",
             "Lê as EFD ICMS/IPI e EFD Contribuições (.txt) para o banco local. A importação roda em segundo "
             "plano: você pode trocar de tela enquanto ela acontece. Ela só para se o programa for fechado "
             "(janela preta) ou se você clicar em Cancelar.", "Dados")
g = ui.gerenciador()

SIT = {"na fila": "Na fila", "lendo": "Lendo", "carregado": "Carregado", "duplicado": "Já existia",
       "erro": "Não carregado", "cancelado": "Cancelado"}


def _tempo(s: float) -> str:
    s = int(s)
    return f"{s // 3600}h{(s % 3600) // 60:02d}min" if s >= 3600 else f"{s // 60}min{s % 60:02d}s"


@st.fragment(run_every=1.5)
def painel_importacao() -> None:
    job = g.atual
    if job is None:
        return
    r = job.resumo()
    ui.secao("Importação atual")
    if r["rodando"]:
        restante = ""
        if r["progresso"] > 0.02:
            restante = f" · faltam cerca de {_tempo(r['decorrido'] * (1 - r['progresso']) / r['progresso'])}"
        if r["n_feitos"] >= r["n_total"]:
            txt = f"Arquivos lidos · preparando as análises · {_tempo(r['decorrido'])} decorridos"
        else:
            txt = (f"{int(r['progresso'] * 100)}% · arquivo {r['n_feitos'] + 1} de {r['n_total']} · "
                   f"{_tempo(r['decorrido'])} decorridos{restante}")
        st.progress(r["progresso"], text=txt)
        st.caption(f"Etapa: {r['etapa']}" + (f" · {r['atual']} ({int(r['atual_progresso'] * 100)}%)"
                                             if r["atual"] else ""))
        if st.button("Cancelar importação", icon=":material/cancel:"):
            job.cancelar()
            st.toast("Cancelando: o arquivo em leitura é descartado; os já concluídos permanecem.")
    else:
        if r["erro_final"]:
            st.error(f"Importação interrompida ({r['erro_final']}).", icon=":material/error:")
        else:
            st.success(f"Concluída em {_tempo(r['decorrido'])}: {r['n_carregados']} carregado(s), "
                       f"{r['n_erros']} com erro, de {r['n_total']} arquivo(s).", icon=":material/check_circle:")
        st.session_state["_import_visto"] = id(job)
    tab = pd.DataFrame([{"Arquivo": a.nome, "Tamanho (MB)": a.tamanho_mb, "Situação": SIT.get(a.situacao, a.situacao),
                         "Progresso": a.progresso, "Tempo (s)": a.segundos, "Mensagem": a.mensagem}
                        for a in job.arquivos])
    st.dataframe(tab, hide_index=True, width="stretch", column_config={
        "Progresso": st.column_config.ProgressColumn("Progresso", min_value=0.0, max_value=1.0, format="percent"),
        "Tamanho (MB)": st.column_config.NumberColumn(format="localized")})
    avisos = [(a.nome, x) for a in job.arquivos for x in a.avisos]
    if avisos:
        with st.expander(f"Avisos de leitura ({len(avisos)})"):
            st.dataframe(pd.DataFrame(avisos, columns=["Arquivo", "Aviso"]), hide_index=True,
                         width="stretch")
    if not r["rodando"] and st.session_state.get("_import_recarregado") != id(job):
        st.session_state["_import_recarregado"] = id(job)
        st.rerun()  # atualiza a lista de arquivos no banco


# ---------------------------------------------------------------- nova importacao
ui.secao("Nova importação", "Informe a pasta onde estão as EFDs. São lidos todos os .txt da pasta e das "
         "subpastas; o tipo (ICMS/IPI ou Contribuições) é reconhecido automaticamente.")
with st.expander("Como copiar o caminho da pasta no Windows Explorer"):
    st.markdown(
        """
1. Abra a pasta das EFDs no Windows Explorer.
2. Clique uma vez na **barra de endereço** (no alto da janela, onde aparece o nome da pasta).
3. O caminho fica selecionado (por exemplo `C:\\Users\\voce\\Documents\\EFDs`). Aperte **Ctrl+C**.
4. Volte aqui, clique no campo **Pasta das EFDs** e aperte **Ctrl+V**.
5. Clique em **Verificar pasta**: aparece a lista de arquivos com o tamanho de cada um.
6. Clique em **Iniciar importação**. A barra de progresso aparece aqui e na barra lateral.
""")
arq_ultima = pasta_dados() / "ultima_pasta.txt"
ultima = arq_ultima.read_text(encoding="utf-8") if arq_ultima.exists() else ""
c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
pasta = c1.text_input("Pasta das EFDs", value=ultima, placeholder=r"C:\Users\voce\Documents\EFDs")
if c2.button("Verificar pasta", width="stretch", disabled=not pasta.strip()):
    try:
        st.session_state["_arquivos_pasta"] = [str(p) for p in listar_txt(pasta)]
        arq_ultima.write_text(pasta.strip().strip('"'), encoding="utf-8")
    except ErroEFD as e:
        st.session_state["_arquivos_pasta"] = []
        st.error(str(e))

lista = st.session_state.get("_arquivos_pasta") or []
if lista:
    from pathlib import Path
    caminhos = [Path(p) for p in lista if Path(p).exists()]
    tam = [p.stat().st_size for p in caminhos]
    ui.cartoes({"Arquivos .txt": ui.formatar_num(len(caminhos)),
                "Tamanho total": f"{ui.formatar_num(sum(tam) / 1e9, 2)} GB" if sum(tam) >= 1e9
                else f"{ui.formatar_num(sum(tam) / 1e6, 1)} MB",
                "Maior arquivo": f"{ui.formatar_num(max(tam) / 1e6, 0)} MB" if tam else "-"})
    if sum(tam) > 1e9:
        st.info("Arquivos grandes: a leitura usa pouca memória (arquivo lido em partes) e leva alguns minutos "
                "por GB. Arquivos já importados são reconhecidos em segundos e pulados.",
                icon=":material/info:")
    with st.expander(f"Ver os {len(caminhos)} arquivo(s)"):
        st.dataframe(pd.DataFrame({"Arquivo": [p.name for p in caminhos],
                                   "Tamanho (MB)": [round(t / 1e6, 1) for t in tam],
                                   "Pasta": [str(p.parent) for p in caminhos]}),
                     hide_index=True, width="stretch")
    if st.button("Iniciar importação", type="primary", icon=":material/play_arrow:", disabled=g.rodando):
        try:
            g.iniciar(caminhos, lambda: ui._conexao_base().cursor(), ui.ao_final_da_importacao)
            st.session_state["_arquivos_pasta"] = []
            time.sleep(0.3)
            st.rerun()
        except RuntimeError as e:
            st.warning(str(e))
elif g.rodando:
    st.caption("Há uma importação em andamento; aguarde para iniciar outra.")

painel_importacao()

# ---------------------------------------------------------------- arquivos no banco
ui.secao("Arquivos no banco", "'Substituído' = havia outra versão do mesmo CNPJ/IE/período; só a mais recente "
         "(retificadora) é usada nos cálculos.")
with ui.protegido("listar os arquivos carregados"):
    tab = qualidade.arquivos_carregados(con)
    if tab.empty:
        ui.vazio("Nenhum arquivo carregado ainda", "Informe a pasta acima e clique em Iniciar importação.")
    else:
        ui.tabela(tab.rename(columns={"tipo": "Tipo", "ie": "IE", "nome": "Razão social", "periodo": "Período",
                                      "versao_layout": "Leiaute", "retificadora": "Retificadora",
                                      "situacao": "Situação", "qtd_linhas": "Linhas",
                                      "carregado_em": "Carregado em"}), moeda=[], altura=380)

with st.expander("Apagar todos os dados carregados"):
    st.write("Remove do banco local todos os arquivos já lidos. Os .txt originais e os parâmetros "
             "(pasta data/params) não são apagados.")
    if g.rodando:
        st.caption("Indisponível durante a importação.")
    confirma = st.checkbox("Confirmo que quero apagar os dados carregados", disabled=g.rodando)
    if st.button("Apagar dados", disabled=not confirma or g.rodando, icon=":material/delete:"):
        with ui.protegido("apagar os dados"):
            from zfm.importacao import TRAVA_BANCO
            with TRAVA_BANCO:
                db.apagar_dados(con)
            st.cache_data.clear()
            st.success("Dados apagados.")
            st.rerun()
