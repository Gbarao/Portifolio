import streamlit as st

from zfm import conciliacoes, ui

ui.cabecalho(
    "6. Apurações",
    "Para que serve: ver as apurações de ICMS (E110/E111/E116), IPI (E520) e PIS/COFINS (bloco M) "
    "mês a mês e conferir se batem com os documentos. O que fazer: confira os ajustes por classe "
    "(crédito estímulo, fundos) e os saldos credores.",
)
con = ui.conexao()
sel = ui.seletor_empresas(con)
if con is None:
    st.stop()
if not ui.preparar(con):
    ui.aviso_sem_dados()
    st.stop()
raizes = ui.raizes_analise(con, sel)
ui.exigir_empresas(raizes)
nomes = ui.nomes_empresas()
f = lambda df: df[df["raiz"].isin(raizes)] if not df.empty else df  # noqa: E731

with ui.protegido("montar a tela de apurações"):
    t1, t2, t3 = st.tabs(["ICMS", "IPI", "PIS/COFINS"])
    with t1:
        ap = f(con.execute("SELECT * FROM v_apur_icms ORDER BY cnpj_estab, mes").df())
        cols = ["debitos", "creditos", "saldo_apurado", "deducoes", "icms_recolher",
                "saldo_credor_transportar", "credito_estimulo", "fundos"]
        long = ap.melt(id_vars=["raiz", "mes"], value_vars=cols, var_name="medida")
        ui.tabela(ui.por_empresa(long, ["medida", "mes"], "value", nomes))
        st.markdown("**Ajustes E111/E116 por classe**")
        aj = f(con.execute("SELECT * FROM v_ajustes_icms").df())
        ui.tabela(ui.por_empresa(aj, ["registro", "classe", "codigo"], "valor", nomes))
        if not aj.empty and aj["nao_classificado"].any():
            st.warning("Há códigos sem classificação: classifique em Parâmetros > Códigos de ajuste.")
        st.markdown("**Conciliação documentos × E110 (Q5)**")
        q5 = conciliacoes.filtrar(conciliacoes.q5_docs_x_e110(con), raizes)
        st.success("Fecha em todos os meses.") if q5.empty else ui.tabela(q5)
    with t2:
        ap = f(con.execute("SELECT * FROM v_apur_ipi ORDER BY cnpj_estab, mes").df())
        long = ap.melt(id_vars=["raiz", "mes"], value_vars=["debitos", "creditos", "saldo_credor",
                                                           "saldo_devedor"], var_name="medida")
        ui.tabela(ui.por_empresa(long, ["medida", "mes"], "value", nomes))
        st.markdown("**Conciliação documentos × E520 (Q6)**")
        q6 = conciliacoes.filtrar(conciliacoes.q6_docs_x_e520(con), raizes)
        st.success("Fecha em todos os meses.") if q6.empty else ui.tabela(q6)
    with t3:
        ap = f(con.execute("SELECT * FROM v_apur_pis_cofins ORDER BY raiz, mes").df())
        cols = ["receita_tributada", "receita_nao_tributada_pis", "pis_nc_periodo",
                "pis_creditos_descontados", "pis_a_recolher", "cofins_nc_periodo",
                "cofins_creditos_descontados", "cofins_a_recolher", "saldo_credito_pis",
                "saldo_credito_cofins"]
        long = ap.melt(id_vars=["raiz", "mes"], value_vars=cols, var_name="medida")
        ui.tabela(ui.por_empresa(long, ["medida", "mes"], "value", nomes))
    st.subheader("Saldos credores no último mês carregado (informação para a transição)")
    leg = con.execute("""
        WITH i AS (SELECT raiz, sum(saldo_credor_transportar) AS icms FROM (
                       SELECT * FROM v_apur_icms
                       QUALIFY mes = max(mes) OVER (PARTITION BY cnpj_estab)) GROUP BY 1),
             p AS (SELECT raiz, sum(saldo_credor) AS ipi FROM (
                       SELECT * FROM v_apur_ipi
                       QUALIFY mes = max(mes) OVER (PARTITION BY cnpj_estab)) GROUP BY 1),
             c AS (SELECT raiz, sum(coalesce(saldo_credito_pis, 0)) AS pis,
                          sum(coalesce(saldo_credito_cofins, 0)) AS cofins FROM (
                       SELECT * FROM v_apur_pis_cofins
                       QUALIFY mes = max(mes) OVER (PARTITION BY raiz)) GROUP BY 1)
        SELECT coalesce(i.raiz, p.raiz, c.raiz) AS raiz, i.icms, p.ipi, c.pis, c.cofins
        FROM i FULL JOIN p ON p.raiz = i.raiz FULL JOIN c ON c.raiz = coalesce(i.raiz, p.raiz)""").df()
    leg = f(leg)
    leg["empresa"] = leg["raiz"].map(lambda r: nomes.get(r, r))
    ui.tabela(leg[["empresa", "raiz", "icms", "ipi", "pis", "cofins"]])
