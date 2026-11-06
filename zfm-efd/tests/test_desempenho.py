"""Desempenho: arquivo sintetico de ~1 milhao de linhas (SPEC 9)."""
from __future__ import annotations

import time
import tracemalloc

import pytest

from tests.fixtures.gerador import gerar_icms, montar_cenario
from zfm.parsers import carregar_arquivo

LINHAS_ALVO = 1_000_000
LIMITE_SEGUNDOS = 180  # "tempo razoavel" (aqui: ~10 s sem medicao de memoria)
LIMITE_MEMORIA_MB = 200


def _arquivo_grande(caminho, linhas_alvo: int) -> int:
    emp = montar_cenario(meses=(1,))
    txt = gerar_icms(emp[0].estabs[0], 1)
    linhas = txt.split("\r\n")
    ini = next(i for i, l in enumerate(linhas) if l.startswith("|C100|"))
    fim = next(i for i, l in enumerate(linhas) if l.startswith("|C990|"))
    bloco = linhas[ini:fim]
    repeticoes = max(1, (linhas_alvo - len(linhas)) // len(bloco))
    total = 0
    with open(caminho, "wb") as f:
        for l in linhas[:ini]:
            f.write((l + "\r\n").encode("latin-1"))
            total += 1
        corpo = ("\r\n".join(bloco) + "\r\n").encode("latin-1")
        for _ in range(repeticoes):
            f.write(corpo)
            total += len(bloco)
        for l in linhas[fim:]:
            if l:
                f.write((l + "\r\n").encode("latin-1"))
                total += 1
    return total


@pytest.mark.lento
def test_um_milhao_de_linhas(con, tmp_path):
    p = tmp_path / "grande.txt"
    total = _arquivo_grande(p, LINHAS_ALVO)
    assert total >= 990_000
    tracemalloc.start()
    t0 = time.perf_counter()
    r = carregar_arquivo(con, p)
    dt = time.perf_counter() - t0
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert r.situacao == "carregado", r.mensagem
    n = con.execute("SELECT count(*) FROM raw_icms_c100").fetchall()[0][0]
    assert n > 200_000
    print(f"\n{total:,} linhas em {dt:.1f}s; pico de memoria Python {pico / 1e6:.0f} MB")
    assert dt < LIMITE_SEGUNDOS
    assert pico / 1e6 < LIMITE_MEMORIA_MB
