import zipfile
from pathlib import Path

import pytest

from consulta_simples.dados_abertos import consultar_offline, detecta_colunas

LINHAS = [
    '"56228356";"N";"00000000";"00000000";"N";"00000000";"00000000"',
    '"11222333";"S";"20200101";"00000000";"N";"00000000";"00000000"',
    '"99887766";"N";"20150101";"20180331";"N";"00000000";"00000000"',
]


@pytest.fixture
def arquivo_simples(tmp_path: Path) -> Path:
    destino = tmp_path / "Simples.zip"
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("F.K03200$W.SIMPLES.CSV.D50510", "\n".join(LINHAS).encode("latin-1"))
    return destino


def test_deteccao_de_colunas():
    colunas = detecta_colunas([l.replace('"', "").split(";") for l in LINHAS])
    assert colunas["raiz"] == 0
    assert colunas["opcao_simples"] == 1
    assert colunas["opcao_mei"] == 4
    assert colunas["data_opcao_simples"] == 2


def test_cruzamento(arquivo_simples: Path):
    linhas = {
        l["cnpj"]: l
        for l in consultar_offline(
            ["11222333000181", "56228356000131", "99887766000100", "12345678000195"],
            arquivo_simples,
        )
    }
    assert linhas["11222333000181"]["optante_simples"] == "SIM"
    assert "desde 01/01/2020" in linhas["11222333000181"]["situacao_simples"]
    assert linhas["56228356000131"]["optante_simples"] == "NAO"
    assert "excluido em 31/03/2018" in linhas["99887766000100"]["situacao_simples"]
    assert linhas["12345678000195"]["status"] == "NAO_ENCONTRADO"
