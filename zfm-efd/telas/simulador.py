import datetime as _dt
from decimal import Decimal as D

import pandas as pd
import streamlit as st

from zfm import params, regras_zfm as rz, ui

ui.marca()
ui.cabecalho("Simulador individual",
             "Calcula uma operação em qualquer um dos seis cenários (LC 214/2025, arts. 443 a 455), com os requisitos, "
             "a memória de cálculo e o efeito no preço. Percentuais e vigências vêm de Parâmetros > Regras legais; "
             "as alíquotas de CBS/IBS/IPI são premissas de simulação.", "Análise")

CENARIOS = {
    "1 – Importação por indústria incentivada (art. 443)": "443",
    "1 – Importação para revenda presencial (art. 444)": "444",
    "2 – Compra de outra UF por contribuinte da ZFM (arts. 445 a 447)": "445",
    "3 – Intermediário ZFM → ZFM entre indústrias incentivadas (arts. 448 e 449)": "448",
    "4 – Venda de produto industrializado na ZFM: IBS sobre o saldo devedor (art. 450)": "450i",
    "4 – Venda de produto industrializado na ZFM: CBS por item (art. 450)": "450c",
    "5 – Venda dentro da ZFM de bem nacional ou serviço prestado na ZFM (art. 451)": "451",
    "6 – IPI: produto existente (art. 454)": "454",
    "6 – IPI: produção futura sem similar nacional (art. 455)": "455",
}
REQ = {
    "443": ["indústria incentivada habilitada", "projeto aprovado", "utilização na ZFM", "bem não excluído (art. 441)",
            "não é uso e consumo pessoal"],
    "444": ["habilitado", "revenda presencial", "ingresso comprovado", "bem não excluído (art. 441)"],
    "445": ["habilitado", "bem industrializado de origem nacional", "ingresso na ZFM comprovado",
            "bem não excluído (art. 441)"],
    "448": ["fornecedor indústria incentivada", "adquirente indústria incentivada", "bem intermediário",
            "bem incorporado/consumido na produção de bem final", "bem não excluído (art. 441)"],
    "450c": ["indústria incentivada habilitada", "fabricação própria conforme projeto", "bem não excluído (art. 441)"],
    "451": ["fornecedor PJ na ZFM", "adquirente na ZFM", "origem nacional (mercadoria)",
            "local físico da prestação na ZFM comprovado"],
}
OPC = {"Atendido": True, "Não atendido": False, "Não comprovado": None}

c1, c2 = st.columns([2, 1])
escolha = c1.selectbox("Cenário", list(CENARIOS))
cod = CENARIOS[escolha]
cen = params.carregar("param_aliquotas_cenario")
cenarios_aliq = list(dict.fromkeys(cen["cenario"]))
ca = c2.selectbox("Premissa de alíquotas", cenarios_aliq, index=cenarios_aliq.index("base") if "base" in cenarios_aliq else 0)
c3, c4, c5, c6 = st.columns(4)
ano = c3.selectbox("Ano", list(range(2027, 2034)), index=2)
linha = cen[(cen.cenario == ca) & (cen.ano == ano)]
a_ibs0 = float(linha["aliq_ibs"].iloc[0]) if len(linha) and pd.notna(linha["aliq_ibs"].iloc[0]) else 0.0
a_cbs0 = float(linha["aliq_cbs"].iloc[0]) if len(linha) and pd.notna(linha["aliq_cbs"].iloc[0]) else 0.0
base = D(str(c4.number_input("Valor/base da operação (R$)", min_value=0.0, value=1000.0, step=100.0)))
a_ibs = D(str(c5.number_input("Alíquota IBS (%)", min_value=0.0, value=a_ibs0, step=0.1, format="%.2f")))
a_cbs = D(str(c6.number_input("Alíquota CBS (%)", min_value=0.0, value=a_cbs0, step=0.1, format="%.2f")))
data = _dt.date(ano, 6, 30)

requisitos = {}
if cod in REQ:
    ui.secao("Requisitos", "Marque só o que está comprovado. 'Não comprovado' gera estimativa com risco.")
    lista = REQ[cod]
    if cod == "451":
        servico = st.toggle("É prestação de serviço", key="sim_srv")
        lista = [x for x in lista if (x != "origem nacional (mercadoria)" or not servico)
                 and (x != "local físico da prestação na ZFM comprovado" or servico)]
    cols = st.columns(2)
    for i, r in enumerate(lista):
        requisitos[r] = OPC[cols[i % 2].radio(r, list(OPC), horizontal=True, key=f"req_{cod}_{i}")]

with ui.protegido("calcular a operação"):
    if cod == "443":
        res = rz.art443_importacao(base, base, a_ibs, a_cbs, data, requisitos)
    elif cod == "444":
        reg = st.toggle("Importador no regime regular", value=True)
        res = rz.art444(base, base, a_ibs, a_cbs, data, reg, requisitos)
    elif cod == "445":
        k1, k2, k3, k4 = st.columns(4)
        uf = k1.selectbox("UF de origem", sorted(rz.UFS - {"AM"}), index=sorted(rz.UFS - {"AM"}).index("SP"))
        ind = k2.toggle("Destinatário indústria incentivada", value=True)
        util = k3.toggle("Utilização na ZFM", value=True)
        regime = k4.selectbox("Regime do destinatário", ["regular", "simples"])
        enc = st.number_input("Industrialização por encomenda: valor agregado (0 = não se aplica)", min_value=0.0, value=0.0)
        res = rz.art445_447(base, a_ibs, a_cbs, uf, data, ind, util, regime, requisitos,
                            D(str(enc)) if enc else None)
    elif cod == "448":
        enc = st.number_input("Industrialização por encomenda: valor agregado (0 = não se aplica)", min_value=0.0, value=0.0)
        res = rz.art448_449(base, data, requisitos, D(str(enc)) if enc else None)
    elif cod == "450i":
        ui.secao("Débitos e créditos de IBS do período", "O crédito presumido incide sobre o saldo devedor de cada "
                 "faixa, nunca sobre a receita. Créditos alocados às faixas na proporção dos débitos.")
        k = st.columns(6)
        deb = {"55": k[0].number_input("Débito IBS – bem final", value=float(base)),
               "75": k[1].number_input("Débito IBS – bem de capital", value=0.0),
               "90_25": k[2].number_input("Débito IBS – intermediário", value=0.0),
               "100_informatica": k[3].number_input("Débito IBS – informática", value=0.0)}
        ne = k[4].number_input("Débito IBS não elegível", value=0.0)
        cred = k[5].number_input("Créditos de IBS do período", value=0.0)
        res = rz.art450_ibs({x: D(str(v)) for x, v in deb.items() if v}, D(str(ne)), D(str(cred)), data)
    elif cod == "450c":
        k1, k2, k3 = st.columns(3)
        e454 = k1.toggle("Produto enquadrado no art. 454", value=False)
        trib = k2.toggle("Operação tributada", value=True)
        o448 = k3.toggle("Operação do art. 448", value=False)
        res = rz.art450_cbs(base, data, e454, trib, o448, requisitos)
    elif cod == "451":
        cred = st.number_input("Créditos de CBS das operações antecedentes (R$)", min_value=0.0, value=0.0)
        res = rz.art451(base, a_ibs, a_cbs, requisitos, D(str(cred)), servico=st.session_state.get("sim_srv", False))
    elif cod == "454":
        k1, k2, k3, k4 = st.columns(4)
        tipi = k1.number_input("TIPI em 31/12/2023 (%)", min_value=0.0, value=5.0)
        ind24 = {"Sim": True, "Não": False, "Não comprovado": None}[k2.radio("Industrializado na ZFM em 2024",
                                                                              ["Sim", "Não", "Não comprovado"])]
        cas = {"Sim": True, "Não": False, "Não comprovado": None}[k3.radio("Projeto CAS 2022–2025",
                                                                            ["Não comprovado", "Sim", "Não"])]
        tic = k4.toggle("TIC excluído da redução", value=False)
        res = rz.art454(D(str(tipi)), ind24, cas, tic, False, base, ano)
    else:
        k1, k2 = st.columns(2)
        alt = k1.selectbox("Alternativa", ["A_cp_cbs_6", "B_ipi_6_5"])
        sim = {"Não": False, "Sim": True, "Não comprovado": None}[k2.radio("Tem similar nacional?",
                                                                            ["Não", "Sim", "Não comprovado"])]
        res = rz.art455(alt, base, sim, data)

    cor = {rz.ELEGIVEL: "success", rz.POTENCIAL: "warning", rz.INSUFICIENTE: "warning", rz.NAO_ELEGIVEL: "error"}
    getattr(st, cor[res.status])(f"{res.status} · confiança {res.confianca}", icon=":material/gavel:")
    ui.secao("Resultado")
    ui.tabela(pd.DataFrame([{"item": k.replace("_", " "), "valor": float(v)} for k, v in res.valores.items()]),
              moeda=["valor"])
    ui.secao("Memória de cálculo")
    st.write(res.memoria())

    ui.secao("Efeito no preço", "IBS/CBS/IPI cobrados por fora (sem a lógica 'por dentro' do ICMS).")
    k1, k2, k3, k4 = st.columns(4)
    prem = k1.selectbox("Premissa de preço", ["liquido_constante", "bruto_constante", "repasse_parcial"],
                        format_func={"liquido_constante": "Preço líquido constante", "bruto_constante":
                                     "Preço bruto constante", "repasse_parcial": "Repasse parcial"}.get)
    ipi = k2.number_input("Alíquota IPI (%)", min_value=0.0, value=0.0)
    repasse = k3.number_input("Repasse (%)", min_value=0.0, max_value=100.0, value=50.0,
                              disabled=prem != "repasse_parcial")
    zero_cbs = k4.toggle("CBS zero na operação (art. 445/448/451)", value=cod in ("445", "448", "451"))
    pr = rz.precos(prem, base, a_ibs if cod not in ("445", "448") else D("0"), D("0") if zero_cbs else a_cbs,
                   D(str(ipi)), repasse_pct=D(str(repasse)))
    ui.cartoes({"Preço líquido": float(pr["preco_liquido"]), "IBS": float(pr["ibs"]), "CBS": float(pr["cbs"]),
                "IPI": float(pr["ipi"]), "Preço bruto": float(pr["preco_bruto"])}, destaque="Preço bruto")
