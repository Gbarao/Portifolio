import streamlit as st

from zfm import conciliacoes, qualidade, ui

ctx = ui.contexto(
    "Qualidade e reconciliação",
    "Confere se os arquivos estão completos e íntegros e se a base de operações explica a apuração "
    "(R5) antes de qualquer simulação. Divergências não impedem a análise, mas aparecem como alerta e, "
    "no caso do R5, como ajuste de reconciliação.", "Dados")
con, f = ctx.con, ctx.filtro

CORES = {qualidade.OK: "background-color:#E7F5EE;color:#1E7B4F",
         qualidade.FALTA_ICMS: "background-color:#FDECEA;color:#B42318",
         qualidade.FALTA_CONTRIB: "background-color:#FDECEA;color:#B42318",
         qualidade.FALTAM_AMBAS: "background-color:#F9D5D1;color:#B42318"}

with ui.protegido("verificar a qualidade"):
    with st.spinner("Conferindo arquivos e conciliações..."):
        q1 = ui.calcular("q1", f, mes_fim=f.mes_fim)
        q1 = q1[q1["raiz"].isin(ctx.raizes)] if not q1.empty else q1
        meses = [m for m in qualidade.MESES[:f.mes_fim]]
        faltas = int((q1[meses] != qualidade.OK).sum().sum()) if not q1.empty else 0
        q2 = qualidade.q2_integridade(con)
        q2 = q2[q2["cnpj"].str[:8].isin(ctx.raizes)] if not q2.empty else q2
        resultados = {cod: ui.calcular("conciliacao", f, q=cod) for cod in conciliacoes.CHECAGENS}
        r5 = ui.calcular("r5", f)
        r5_nao = r5[~r5["fecha"]] if not r5.empty else r5

    n_div = sum(len(d) > 0 for d in resultados.values())
    ui.cartoes({"Completude (Q1)": ("OK" if faltas == 0 else f"{faltas} falta(s)", "estabelecimento × mês"),
                "Integridade (Q2)": ("OK" if q2.empty else f"{len(q2)} divergência(s)", "bloco 9 × lido"),
                "Conciliações Q3–Q17": ("OK" if n_div == 0 else f"{n_div} com divergência",
                                        f"{len(resultados)} checagens"),
                "Reconciliação R5": ("OK" if r5_nao.empty else f"{len(r5_nao)} não fecham",
                                     "base de operações × apuração")})

    t1, tfc, t2, t3, t4 = st.tabs(["Completude e integridade", "Fiscal × Contribuições", "Conciliações",
                                   "Reconciliação R5", "Avisos de leitura"])
    with tfc:
        ui.secao("Pareamento dos documentos entre as duas EFDs",
                 "Cada C100 é procurado na outra EFD por estabelecimento + entrada/saída + chave da NF-e (sem chave: "
                 "modelo, série, número, data e CNPJ do participante). Só 'Só na EFD ICMS/IPI' e 'Só na EFD "
                 "Contribuições' são divergências; as demais situações são esperadas e explicadas abaixo.")
        pr = ui.calcular("pareamento", f)
        pr = pr[pr["raiz"].isin(ctx.raizes)] if not pr.empty else pr
        if pr.empty:
            ui.vazio("Sem documentos C100 nas EFDs")
        else:
            piv = pr.pivot_table(index=["fonte", "sentido", "situacao"], values=["documentos", "valor"],
                                 aggfunc="sum").reset_index()
            ui.tabela(piv, moeda=["valor"])
            with st.expander("O que significa cada situação"):
                st.markdown(
                    "- **Nas duas EFDs:** documento encontrado nas duas; valores, data e participante conferidos (Q7) "
                    "e CFOPs/itens conferidos (Q15).\n"
                    "- **Só na EFD ICMS/IPI / Só na EFD Contribuições:** as duas EFDs do mês estão carregadas e o "
                    "documento está só numa. Divergência (Q7).\n"
                    "- **Só na EFD ICMS/IPI (entrada sem crédito?):** entrada sem PIS/COFINS a creditar pode não constar "
                    "da EFD Contribuições. Não é tratada como erro.\n"
                    "- **Contribuições consolidada:** o estabelecimento escritura a Contribuições por C180/C190 (sem "
                    "documento); a conferência é pelo total (C180 × C190, Q7).\n"
                    "- **Sem contrapartida:** a outra EFD daquele mês não foi carregada (ver cobertura).\n"
                    "- **Repetido na mesma EFD:** segunda ocorrência do documento (Q16).")
        ui.secao("Cobertura: EFD ICMS/IPI de cada estabelecimento × EFD Contribuições da empresa")
        cob = ui.calcular("cobertura", f)
        cob = cob[cob["raiz"].isin(ctx.raizes)] if not cob.empty else cob
        if not cob.empty:
            fl = cob[~cob["situacao"].str.startswith("OK")]
            if fl.empty:
                st.success("As duas EFDs estão carregadas para todos os estabelecimentos do AM em todos os meses.",
                           icon=":material/check_circle:")
            else:
                st.error(f"{len(fl)} combinação(ões) estabelecimento × mês com EFD faltando.", icon=":material/error:")
                ui.tabela(fl.drop(columns=["no_0140"]), moeda=[])
    with t1:
        ui.secao("Q1 – As duas EFDs existem em todos os meses?",
                 "A EFD Contribuições é entregue pela matriz; por isso é procurada pela raiz do CNPJ. "
                 "Só estabelecimentos do Amazonas.")
        if q1.empty:
            ui.vazio("Sem estabelecimentos do AM no período")
        else:
            if faltas:
                st.error(f"{faltas} combinação(ões) estabelecimento × mês com arquivo faltando. Importe o arquivo "
                         "que falta em Dados > Importação.", icon=":material/error:")
            vis = q1.rename(columns={"raiz": "Raiz CNPJ", "cnpj": "CNPJ", "ie": "IE", "nome": "Razão social"})
            st.dataframe(vis.style.map(lambda v: CORES.get(v, ""), subset=meses), hide_index=True,
                         width="stretch")
        ui.secao("Q2 – As contagens do bloco 9 batem com o que foi lido?")
        if q2.empty:
            st.success("Nenhuma divergência nos registros 9900 e 9999.", icon=":material/check_circle:")
        else:
            st.error(f"{len(q2)} divergência(s): o arquivo pode estar incompleto ou alterado.",
                     icon=":material/error:")
            ui.tabela(q2, moeda=[])
    with t2:
        ui.secao("Conciliações entre registros", "Cada checagem lista o que não fecha (tolerâncias em "
                 "Parâmetros > Premissas).")
        resumo = [{"Checagem": cod, "Descrição": titulo, "Situação": "OK" if resultados[cod].empty else
                   f"{len(resultados[cod])} divergência(s)"} for cod, (titulo, _) in conciliacoes.CHECAGENS.items()]
        st.dataframe(resumo, hide_index=True, width="stretch")
        com = [c for c in conciliacoes.CHECAGENS if not resultados[c].empty]
        if com:
            cod = st.selectbox("Ver divergências de", com,
                               format_func=lambda c: f"{c} – {conciliacoes.CHECAGENS[c][0]}")
            ui.tabela(resultados[cod], altura=380)
            ui.baixar_csv(resultados[cod], f"conciliacao_{cod}")
    with t3:
        ui.secao("R5 – Carga recalculada pela base de operações × carga da apuração",
                 "Troca os débitos e créditos da apuração pelos da base de operações (ajustes, deduções e saldos "
                 "continuam os da apuração) e compara. O que não fecha entra no relatório como 'ajuste de "
                 "reconciliação' e aparece no To Be separado do efeito da reforma.")
        if r5.empty:
            ui.vazio("Sem apuração no período")
        elif r5_nao.empty:
            st.success("A base de operações explica a apuração em todos os meses e tributos.",
                       icon=":material/check_circle:")
        else:
            st.warning(f"{len(r5_nao)} combinação(ões) empresa × mês × tributo não fecham.", icon=":material/warning:")
            ui.tabela(r5_nao)
        with st.expander("R5 completo"):
            ui.tabela(r5)
            ui.baixar_csv(r5, "reconciliacao_r5")
    with t4:
        av = qualidade.avisos_carga(con)
        if av.empty:
            ui.vazio("Nenhum aviso de leitura")
        else:
            ui.tabela(av, moeda=[])
