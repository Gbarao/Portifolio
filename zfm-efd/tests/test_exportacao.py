"""Exportacao: o Excel reproduz os numeros e lista as premissas."""
from __future__ import annotations

import io

import openpyxl
import pytest

from zfm import beneficio_atual as ba
from zfm import exportacao


def test_excel(con_param):
    dados = exportacao.gerar_excel(con_param, None, False, False)
    wb = openpyxl.load_workbook(io.BytesIO(dados), data_only=True)
    for aba in ("Resumo", "Benefício atual", "Simulação", "Teste de absorção", "Premissas adotadas", "Parâmetros (tabelas)",
                "Simulação saídas x entradas",
                "Apuração ICMS", "Completude Q1"):
        assert aba in wb.sheetnames, aba
    ws = wb["Benefício atual"]
    cab = [c.value for c in ws[1]]
    i_tot = cab.index("Total")
    total_excel = sum(r[i_tot] for r in ws.iter_rows(min_row=2, values_only=True))
    assert total_excel == pytest.approx(ba.calcular(con_param)["beneficio"].sum(), abs=0.01)
    prem = [r[0] for r in wb["Parâmetros (tabelas)"].iter_rows(values_only=True)]
    assert any(str(x).startswith("### Alíquotas por cenário") for x in prem)


def test_excel_uma_empresa(con_param):
    dados = exportacao.gerar_excel(con_param, ["22222222"], False, False)
    wb = openpyxl.load_workbook(io.BytesIO(dados))
    cab = [c.value for c in wb["Benefício atual"][1]]
    assert "Total" in cab and len(cab) == 3  # tributo, Beta, Total
