"""Importacao em segundo plano: continua sozinha e pode ser cancelada sem deixar arquivo parcial."""
from __future__ import annotations

import time

from tests.fixtures.gerador import gerar_conjunto
from zfm import db, visoes
from zfm.importacao import Gerenciador


def _esperar(job, limite=300):
    t = time.time()
    while job.rodando and time.time() - t < limite:
        time.sleep(0.2)


def test_importacao_em_segundo_plano(con, tmp_path):
    pasta = tmp_path / "efd"
    arquivos = gerar_conjunto(pasta)
    g = Gerenciador()
    job = g.iniciar(sorted(arquivos), con.cursor, ao_final=visoes.preparar)
    assert job.rodando
    _esperar(job)
    r = job.resumo()
    assert r["etapa"] == "concluída" and r["n_carregados"] == len(arquivos) and r["progresso"] == 1.0
    assert con.execute("SELECT count(*) FROM arquivos WHERE ativo").fetchall()[0][0] == len(arquivos)
    assert con.execute("SELECT count(*) FROM v_base_operacoes").fetchall()[0][0] > 0
    # reimportar: arquivos reconhecidos pela assinatura rapida, sem reler
    job2 = g.iniciar(sorted(arquivos), con.cursor)
    _esperar(job2)
    assert all(a.situacao == "duplicado" for a in job2.arquivos)


def test_cancelar_nao_deixa_arquivo_parcial(con, tmp_path):
    pasta = tmp_path / "grande"
    arquivos = gerar_conjunto(pasta, meses=(1,), escala=12000)
    g = Gerenciador()
    job = g.iniciar(sorted(arquivos), con.cursor)
    while job.rodando and not any(a.situacao == "lendo" and a.progresso > 0 for a in job.arquivos):
        time.sleep(0.05)
    job.cancelar()
    _esperar(job)
    situacoes = {a.situacao for a in job.arquivos}
    assert "cancelado" in situacoes
    # cada arquivo cancelado nao deixou nenhuma linha
    ids = {r[0] for r in con.execute("SELECT nome_arquivo FROM arquivos").fetchall()}
    for a in job.arquivos:
        if a.situacao == "cancelado":
            assert a.nome not in ids
    n_c100 = con.execute("""SELECT count(*) FROM raw_icms_c100 r
                            WHERE r.arquivo_id NOT IN (SELECT arquivo_id FROM arquivos)""").fetchall()[0][0]
    assert n_c100 == 0


def test_uma_importacao_por_vez(con, tmp_path):
    import pytest
    arquivos = gerar_conjunto(tmp_path / "g", meses=(1,), escala=500)
    g = Gerenciador()
    job = g.iniciar(sorted(arquivos), con.cursor)
    with pytest.raises(RuntimeError):
        g.iniciar(sorted(arquivos), con.cursor)
    job.cancelar()
    _esperar(job)
