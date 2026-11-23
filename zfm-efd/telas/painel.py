import plotly.graph_objects as go
import streamlit as st

from zfm import params, qualidade, simulacao, ui

ui.marca()
con = ui.conexao()
if con is None:
    st.stop()
sel = ui.seletor_empresas(con)
tem = ui.preparar(con)

if not tem or (ui.importacao_rodando() and not ui.analises_prontas(con)):
    ui.cabecalho("Painel", "Análise da Zona Franca de Manaus na Reforma Tributária: carga atual lida da "
                 "apuração (As Is) × carga simulada de 2027 a 2033 (To Be), por cenário, empresa e tributo.",
                 "Visão geral")
    ui.aviso_importacao(con)
    ui.vazio("Nenhuma EFD carregada",
             "Comece pela tela Importação das EFDs (menu à esquerda, seção Dados).")
    ui.passos([
        ("1. Importar as EFD ICMS/IPI e EFD Contribuições (.txt)", False, "Dados > Importação das EFDs"),
        ("2. Conferir completude e reconciliação", False, "Dados > Qualidade e conferências"),
        ("3. Revisar parâmetros: Empresas ZFM, Produtos (TIPI), códigos de ajuste", False,
         "Dados > Cadastros"),
        ("4. Analisar cenários e diferença As Is × To Be", False, "Análise"),
        ("5. Exportar para Excel", False, "Relatórios"),
    ])
    st.stop()

raizes = ui.raizes_analise(con, sel)
nomes = ui.nomes_empresas()
ano_b = params.ano_base(con)
ui.cabecalho("Painel", "Situação dos dados, pendências e resultado consolidado. Diferença = carga To Be − "
             "carga As Is (positivo = a empresa paga mais).", "Visão geral",
             ["Consolidado do grupo" if sel is None else f"{len(raizes)} empresa(s)", f"Ano-base {ano_b}"])
ui.aviso_importacao(con)

with ui.protegido("montar o painel"):
    # ------------------------------------------------------------- diagnostico
    d = con.execute("""
        SELECT count(*) FILTER (WHERE ativo), count(*) FILTER (WHERE ativo AND tipo = 'ICMS_IPI'),
               count(*) FILTER (WHERE ativo AND tipo = 'CONTRIB'), count(DISTINCT raiz) FILTER (WHERE ativo),
               string_agg(DISTINCT CAST(year(dt_ini) AS VARCHAR), ', ') FILTER (WHERE ativo),
               sum(qtd_linhas) FILTER (WHERE ativo)
        FROM arquivos""").fetchall()[0]
    n_est = con.execute("SELECT count(*) FROM v_estabelecimentos WHERE no_amazonas").fetchall()[0][0]
    n_base = con.execute("SELECT count(*) FROM v_base_operacoes").fetchall()[0][0]
    ui.cartoes({"Arquivos em uso": (ui.formatar_num(d[0]), f"{d[1]} ICMS/IPI · {d[2]} Contribuições"),
                "Empresas (raiz CNPJ)": (ui.formatar_num(d[3]), f"{n_est} estabelecimento(s) no AM"),
                "Anos carregados": (d[4] or "-", f"análise sobre {ano_b}"),
                "Linhas lidas": (ui.formatar_num(d[5] or 0), f"{ui.formatar_num(n_base)} operações na base")})

    problemas = []
    if n_est == 0:
        problemas.append("Nenhum estabelecimento do grupo está no Amazonas (UF do registro 0000). As análises "
                         "consideram apenas estabelecimentos do AM.")
    if d[2] == 0:
        problemas.append("Nenhuma EFD Contribuições carregada: PIS/COFINS e saídas por produto ficam vazios.")
    if d[1] == 0:
        problemas.append("Nenhuma EFD ICMS/IPI carregada: ICMS, IPI e entradas ficam vazios.")
    if n_base == 0 and d[0]:
        problemas.append("A base de operações está vazia. Verifique se os CFOPs foram classificados "
                         "(Cadastros > CFOPs) e se os arquivos são do período esperado.")
    if not raizes:
        problemas.append("Nenhuma empresa selecionada (barra lateral) ou todas marcadas para não entrar na "
                         "análise (Cadastros > Empresas).")
    for p in problemas:
        st.warning(p, icon=":material/warning:")
    if not raizes:
        st.stop()

    from zfm.filtros import Filtro
    _, mes_fim = qualidade.periodo_padrao(con)
    f = Filtro(raizes=tuple(raizes), mes_ini=1, mes_fim=max(mes_fim, 1))

    # ------------------------------------------------------------- checklist
    cob = ui.calcular("cobertura", f)
    cob = cob[cob["raiz"].isin(raizes)] if not cob.empty else cob
    faltas = int((~cob["situacao"].str.startswith("OK")).sum()) if not cob.empty else 0
    r5 = ui.calcular("r5", f)
    r5_nao = int((~r5["fecha"]).sum()) if not r5.empty else 0
    ez = params.carregar("param_empresas_zfm")
    ez_pend = int((~ez["revisado"]).sum()) if not ez.empty else 0
    prod = params.carregar("param_produtos")
    sem_tipi = int((prod["incentivado"] & prod["aliq_ipi"].isna()).sum()) if not prod.empty else 0
    mat = ui.calcular("matriz", f)
    nc = mat[mat["cenario"].isin(["NC_S", "NC_E"])] if not mat.empty else mat
    nc_v = float(nc["valor"].sum()) if not nc.empty else 0.0

    c1, c2 = st.columns([1.05, 1])
    with c1:
        ui.secao("Roteiro e pendências")
        ui.passos([
            ("EFDs importadas", d[0] > 0, f"{d[0]} arquivo(s), meses 1 a {mes_fim} de {ano_b}"),
            ("EFD ICMS/IPI e EFD Contribuições de cada empresa em todos os meses", faltas == 0,
             "OK" if faltas == 0 else f"{faltas} escrituração(ões) faltando (veja Importação)"),
            ("Reconciliação R5: a base explica a apuração", r5_nao == 0,
             "OK" if r5_nao == 0 else f"{r5_nao} combinação(ões) não fecham (vira ajuste de reconciliação)"),
            ("Empresas ZFM revisadas (tipo e regime)", ez_pend == 0,
             "OK" if ez_pend == 0 else f"{ez_pend} CNPJ(s) com classificação automática"),
            ("Produtos incentivados com alíquota TIPI", sem_tipi == 0,
             "OK" if sem_tipi == 0 else f"{sem_tipi} produto(s) sem TIPI"),
            ("Operações classificadas nos cenários", nc.empty,
             "OK" if nc.empty else f"{ui.formatar_brl_curto(nc_v)} em operações não classificadas"),
        ])
    with c2:
        ui.secao("Resultado consolidado", "Cenário de alíquotas 'base', ano inteiro de 2027 a 2033.")
        anual, _ = ui.calcular("simular", f, False)
        if anual.empty:
            ui.vazio("Sem simulação", "Sem dados suficientes para simular.")
        else:
            ev = simulacao.diferenca_por_tributo(anual[anual.cenario == "base"]).groupby(
                "ano", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
            a33 = ev[ev.ano == 2033]
            if not a33.empty:
                ui.cartoes({"Carga As Is (anualizada)": float(a33["as_is"].iloc[0]),
                            "Carga To Be 2033": float(a33["to_be"].iloc[0])})
                ui.cartoes({"Diferença 2033": (float(a33["diferenca"].iloc[0]), "+ paga mais · − paga menos")},
                           sinal=True)
            cores = ["#B42318" if v > 0 else "#1E7B4F" for v in ev["diferenca"]]
            fig = go.Figure(go.Bar(x=ev["ano"].astype(str), y=ev["diferenca"], marker_color=cores,
                                   text=[ui.formatar_brl_curto(v) for v in ev["diferenca"]],
                                   textposition="outside", name="Diferença"))
            fig.update_layout(showlegend=False, yaxis_title="Diferença (R$)")
            fig.update_xaxes(type="category")
            ui.grafico(fig, 300)

    ui.secao("Diferença por empresa (2033, cenário base)")
    if not anual.empty:
        r = anual[(anual.cenario == "base") & (anual.ano == 2033)][
            ["raiz", "as_is_total", "to_be_total", "diferenca_total", "perda_vantagem_ipi"]].copy()
        r.insert(0, "empresa", r["raiz"].map(lambda x: nomes.get(x, x)))
        ui.tabela(r.sort_values("diferenca_total", ascending=False).rename(columns={
            "as_is_total": "As Is (R$)", "to_be_total": "To Be 2033 (R$)", "diferenca_total": "Diferença (R$)",
            "perda_vantagem_ipi": "Perda de vantagem IPI (R$)"}),
            moeda=["As Is (R$)", "To Be 2033 (R$)", "Diferença (R$)", "Perda de vantagem IPI (R$)"])

    al = ui.calcular("alertas", f)
    ui.secao("Alertas principais", "Lista completa em Análise > Cenários ZFM > Pendências.")
    if al.empty:
        st.success("Nenhum alerta.", icon=":material/check_circle:")
    else:
        res = al.groupby(["gravidade", "tipo", "onde_corrigir"], as_index=False, sort=False).agg(
            ocorrencias=("ocorrencias", "sum"), valor=("valor", "sum"))
        ui.tabela(res, moeda=["valor"])
