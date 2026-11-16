"""Exportacao: o Excel reproduz os numeros e lista as premissas."""
from __future__ import annotations

import io

import openpyxl
import pytest

from zfm import exportacao, simulacao
from zfm.filtros import Filtro


def test_excel(con_param):
    dados = exportacao.gerar_excel(con_param, None, False, False)
    wb = openpyxl.load_workbook(io.BytesIO(dados), data_only=True)
    for aba in ("Resumo", "Premissas adotadas", "Diferença por tributo", "Diferença por empresa",
                "Ponte As Is → To Be", "Saídas x entradas", "Vantagem competitiva IPI", "Absorção (anual)",
                "Carga As Is (anual)", "R5 reconciliação", "Benefício ZFM (informativo)",
                "Parâmetros (tabelas)", "Completude Q1"):
        assert aba in wb.sheetnames, aba
    ws = wb["Diferença por empresa"]
    cab = [c.value for c in ws[1]]
    i_c, i_a, i_d = cab.index("cenario"), cab.index("ano"), cab.index("diferenca_total")
    total_excel = sum(r[i_d] for r in ws.iter_rows(min_row=2, values_only=True)
                      if r[i_c] == "base" and r[i_a] == 2033)
    anual, _ = simulacao.simular(con_param)
    esperado = anual[(anual.cenario == "base") & (anual.ano == 2033)]["diferenca_total"].sum()
    assert total_excel == pytest.approx(esperado, abs=0.01)
    prem = [r[0] for r in wb["Parâmetros (tabelas)"].iter_rows(values_only=True)]
    assert any(str(x).startswith("### Alíquotas por cenário") for x in prem)


def test_excel_uma_empresa(con_param):
    dados = exportacao.gerar_excel(con_param, Filtro(raizes=("22222222",)), False, False)
    wb = openpyxl.load_workbook(io.BytesIO(dados))
    cab = [c.value for c in wb["Diferença por tributo"][1]]
    assert cab[-1] == "Total" and len(cab) == 5  # cenario, ano, tributo, Beta, Total
