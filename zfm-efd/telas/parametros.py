import pandas as pd
import streamlit as st

from zfm import params, simulacao, ui

ui.marca()
con = ui.conexao()
if con is None:
    st.stop()
ui.seletor_empresas(con)
tem_dados = ui.preparar(con)
ui.cabecalho("Parâmetros e premissas",
             "Todas as alíquotas, percentuais, fatores e listas usados nos cálculos ficam aqui (nada fixo no "
             "código). Os valores iniciais são hipóteses para validar. Edite na tabela e clique em Salvar, ou "
             "baixe o CSV, edite no Excel e importe de volta.", "Dados")

c1, c2 = st.columns([1, 3], vertical_alignment="center")
if c1.button("Preencher a partir das EFDs", type="primary", disabled=not tem_dados or ui.importacao_rodando(),
             icon=":material/auto_fix_high:", width="stretch"):
    with ui.protegido("preencher os parâmetros a partir das EFDs"):
        from zfm.importacao import TRAVA_BANCO
        with st.spinner("Lendo cadastros das EFDs..."), TRAVA_BANCO:
            n = params.preencher_a_partir_das_efds(con)
        st.success("Linhas novas: " + ", ".join(f"{params.TABELAS[k].titulo}: {v}" for k, v in n.items())
                   + ". Linhas já editadas não foram alteradas.")
c2.caption("Acrescenta empresas, CNPJs do Amazonas (tipo ZFM), produtos (0200), CFOPs e códigos de ajuste "
           "(E111/E116) encontrados nas EFDs, sem apagar o que já foi editado. Roda sozinho ao fim de cada "
           "importação.")

# ---------------------------------------------------------------- pendencias
with ui.protegido("verificar pendências"):
    prod = params.carregar("param_produtos")
    cod = params.carregar("param_codigos_ajuste_icms")
    ez = params.carregar("param_empresas_zfm")
    pend = []
    if not ez.empty and (~ez["revisado"]).any():
        pend.append(f"Empresas ZFM: {int((~ez['revisado']).sum())} CNPJ(s) com tipo/regime definidos automaticamente.")
    if not prod.empty:
        sem_tipi = prod[prod["incentivado"] & prod["aliq_tipi_2023"].isna()]
        if len(sem_tipi):
            pend.append(f"Produtos: {len(sem_tipi)} incentivado(s) sem alíquota TIPI (CP de CBS no percentual "
                        "menor e vantagem competitiva de IPI zero).")
        pc = simulacao.produtos_com_percentuais(prod)
        risco = pc[pc["incentivado"] & pc["alerta_ibs"]]
        if len(risco):
            pend.append(f"Produtos: {len(risco)} com crédito estímulo maior que o percentual do art. 450 "
                        "(candidatos a perda no IBS).")
    if not cod.empty and (cod["classe"] == "nao_classificado").any():
        pend.append(f"Códigos de ajuste: {int((cod['classe'] == 'nao_classificado').sum())} sem classificação.")
    if pend:
        with st.container(border=True):
            st.markdown("**Pendências de revisão**")
            for p in pend:
                st.markdown(f"- {p}")

ORDEM = ["param_empresas_zfm", "param_produtos", "param_regras_cenario", "param_conferencia_cenario",
         "param_aliquotas_cenario", "param_codigos_ajuste_icms", "param_cfops", "param_empresas",
         "param_municipios_zfm", "param_aliquotas_regime_geral", "param_teses", "param_premissas"]
TITULOS = {"param_empresas_zfm": "Empresas ZFM", "param_produtos": "Produtos",
           "param_regras_cenario": "Regras por cenário", "param_conferencia_cenario": "Conferências",
           "param_aliquotas_cenario": "Alíquotas por ano", "param_codigos_ajuste_icms": "Códigos de ajuste",
           "param_cfops": "CFOPs", "param_empresas": "Empresas do grupo", "param_municipios_zfm": "Municípios ZFM",
           "param_aliquotas_regime_geral": "Regime geral", "param_teses": "Teses", "param_premissas": "Premissas"}
abas = st.tabs(["Resumo e alíquotas"] + [TITULOS[n] for n in ORDEM])

SELECOES = {
    "param_empresas_zfm": {"tipo": ["industria_incentivada", "habilitado", "nao_habilitado"],
                           "regime": ["regular", "simples"]},
    "param_produtos": {"tipo_bem": ["final", "capital", "intermediario", "informatica"]},
    "param_regras_cenario": {"entrada_creditavel": ["sim", "nao", "regime"], "cp_ibs_entrada": ["", "447", "449", "444"],
                             "sentido": ["entrada", "saida"]},
    "param_conferencia_cenario": {"tributo": ["ICMS", "IPI", "PIS", "COFINS"],
                                  "regra": ["aliquota_em", "cst_em", "valor_zero"]},
    "param_codigos_ajuste_icms": {"classe": ["credito_estimulo", "credito_presumido_entrada", "fundo_FTI", "fundo_UEA",
                                             "fundo_FMPES", "outros_beneficios", "outros", "nao_classificado"]},
    "param_teses": {"tributo": ["ICMS", "IPI", "PIS", "COFINS"],
                    "tipo_efeito": ["valor_fixo_mensal", "credito_adicional", "reduz_base", "reduz_aliquota"],
                    "status": ["ativa", "em discussão", "simulação apenas"]},
}

with abas[0]:
    with ui.protegido("mostrar as premissas"):
        ui.secao("Alíquotas de referência de CBS e IBS por cenário (%)",
                 "Digite a alíquota cheia de cada cenário e clique em Aplicar. 2027–2028: CBS = referência − "
                 "'reducao_cbs_2027_2028' e IBS teste ('aliq_ibs_teste'); 2029–2032: IBS = referência × (1 − fator "
                 "do ICMS); 2033: referência cheia. Ajuste ano a ano na aba 'Alíquotas por ano'.")
        USAR = "usar tabela de produtos"
        refs = params.aliquotas_referencia()
        refs["ipi_protegido_override"] = refs["ipi_protegido_override"].replace("", USAR).fillna(USAR)
        refs_ed = st.data_editor(
            refs, key="ed_refs", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "cenario": st.column_config.TextColumn("Cenário", required=True),
                "cbs_referencia": st.column_config.NumberColumn("CBS referência (%)", format="%.2f"),
                "ibs_referencia": st.column_config.NumberColumn("IBS referência (%)", format="%.2f"),
                "aplica_cp_450": st.column_config.CheckboxColumn("Aplica CP do art. 450"),
                "ipi_protegido_override": st.column_config.SelectboxColumn(
                    "IPI protegido", options=[USAR, "nao"], help="'nao' = nenhum produto com IPI protegido"),
                "fonte": st.column_config.TextColumn("Fonte / justificativa", width="large"),
            })
        if st.button("Aplicar aos anos 2027–2033", type="primary", key="aplicar_refs"):
            r_ = pd.DataFrame(refs_ed)
            r_["ipi_protegido_override"] = r_["ipi_protegido_override"].replace(USAR, "").fillna("")
            params.aplicar_referencias(r_)
            st.success("Alíquotas recalculadas para 2027–2033.")
            st.rerun()
        ui.secao("Todas as premissas adotadas", "Valor adotado, onde alterar e fonte. A mesma lista vai para o "
                 "Excel (aba 'Premissas').")
        resumo = params.resumo_premissas()
        grupos = ["(todos)"] + list(dict.fromkeys(resumo["grupo"]))
        g = st.selectbox("Grupo", grupos, key="grupo_premissas")
        vis = resumo if g == "(todos)" else resumo[resumo.grupo == g]
        st.dataframe(vis.rename(columns={"grupo": "Grupo", "premissa": "Premissa", "valor_adotado": "Valor adotado",
                                         "onde_alterar": "Onde alterar", "fundamento_fonte": "Fundamento / fonte"}),
                     hide_index=True, width="stretch", height=480)


def editor(nome: str) -> None:
    t = params.TABELAS[nome]
    st.caption(t.ajuda)
    df = params.carregar(nome)
    busca = ""
    if len(df) > 200:
        busca = st.text_input("Buscar (qualquer coluna)", key=f"busca_{nome}", placeholder="Digite parte do texto",
                              help="Filtra a tabela para editar. Ao salvar, as linhas que não aparecem são mantidas.")
    vis = df
    if busca.strip():
        alvo = busca.strip().lower()
        msk = df.astype(str).apply(lambda c: c.str.lower().str.contains(alvo, regex=False)).any(axis=1)
        vis = df[msk]
        st.caption(f"{len(vis)} de {len(df)} linhas.")
    cfg = {c: st.column_config.SelectboxColumn(c, options=o) for c, o in SELECOES.get(nome, {}).items()}
    editado = st.data_editor(vis, key=f"ed_{nome}_{busca}", num_rows="dynamic", hide_index=True,
                             width="stretch", column_config=cfg, height=min(38 * (len(vis) + 2), 520))
    b1, b2, b3 = st.columns([1, 1, 2])
    if b1.button("Salvar", key=f"salvar_{nome}", type="primary", icon=":material/save:", width="stretch"):
        novo = pd.DataFrame(editado)
        if busca.strip():
            resto = df[~df.index.isin(vis.index)]
            novo = pd.concat([resto, novo], ignore_index=True)
        params.salvar(nome, novo)
        st.success("Salvo. Os cálculos já usam os novos valores.")
    b2.download_button("Baixar CSV", params.exportar_csv(nome, df), file_name=f"{nome}.csv", mime="text/csv",
                       key=f"baixar_{nome}", icon=":material/download:", width="stretch")
    with b3.popover("Importar CSV editado no Excel", icon=":material/upload:"):
        arq = st.file_uploader("Arquivo CSV", type=["csv"], key=f"imp_{nome}")
        if arq is not None and st.button("Confirmar importação", key=f"conf_{nome}"):
            try:
                novo = params.importar_csv(nome, arq.getvalue())
                params.salvar(nome, novo)
                st.success(f"Importado: {len(novo)} linhas.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    if nome == "param_produtos" and not df.empty:
        ui.secao("Percentuais calculados (art. 450)", "Não editáveis: derivados de tipo de bem, TIPI e premissas.")
        pc = simulacao.produtos_com_percentuais(df)
        v = pc[["raiz_cnpj", "cod_item", "descricao", "tipo_bem", "aliq_tipi_2023", "nivel_credito_estimulo",
                "p_ibs_450", "p_cbs_450", "alerta_ibs"]].copy()
        v["p_ibs_450"] *= 100
        v["p_cbs_450"] *= 100
        ui.tabela(v.rename(columns={"p_ibs_450": "CP IBS (% do saldo)", "p_cbs_450": "CP CBS (% da venda)",
                                    "alerta_ibs": "Crédito estímulo > CP IBS"}),
                  moeda=[], pct=["CP IBS (% do saldo)", "CP CBS (% da venda)"])
    if nome == "param_regras_cenario":
        st.info("Frações da alíquota do ano: 1 = integral, 0 = zero, 0,7 = 70% (art. 446). As regras valem para "
                "todas as empresas; o cenário de cada operação é definido pelo tipo ZFM (aba Empresas ZFM), pela "
                "origem/destino e pelo CFOP. Ordem de dedução do IBS: premissa 'ordem_deducao_ibs'.",
                icon=":material/info:")


for aba, nome in zip(abas[1:], ORDEM):
    with aba:
        with ui.protegido(f"mostrar {params.TABELAS[nome].titulo}"):
            editor(nome)
