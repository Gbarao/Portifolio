"""Checagens Q1 (completude) e Q2 (integridade do bloco 9)."""
from __future__ import annotations

from zfm import qualidade
from zfm.empresas import empresas, estabelecimentos
from zfm.parsers import carregar_arquivo


def test_estabelecimentos_cadastrados_automaticamente(con_carregado):
    est = estabelecimentos(con_carregado)
    assert set(est["cnpj"]) == {"11111111000191", "11111111000272", "22222222000122",
                                "33333333000133", "33333333000214"}
    fora = est[~est["no_amazonas"]]
    assert list(fora["cnpj"]) == ["33333333000133"]  # matriz da Gama em SP
    emp = empresas(con_carregado)
    assert set(emp["raiz"]) == {"11111111", "22222222", "33333333"}
    assert int(emp.loc[emp.raiz == "11111111", "qtd_estab_am"].iloc[0]) == 2


def test_q1_tudo_completo(con_carregado):
    m = qualidade.q1_completude(con_carregado)
    assert list(m.columns[-3:]) == ["jan", "fev", "mar"]
    assert len(m) == 4  # so os estabelecimentos do AM
    assert (m[["jan", "fev", "mar"]] == qualidade.OK).all().all()


def test_q1_detecta_falta(con, pasta_efd):
    for p in sorted(pasta_efd.glob("*.txt")):
        if p.name in ("EFD_CONTRIB_22222222000122_202602.txt",
                      "EFD_ICMS_IPI_11111111000272_202603.txt"):
            continue
        carregar_arquivo(con, p)
    m = qualidade.q1_completude(con).set_index("cnpj")
    assert m.loc["22222222000122", "fev"] == qualidade.FALTA_CONTRIB
    assert m.loc["11111111000272", "mar"] == qualidade.FALTA_ICMS
    assert m.loc["11111111000191", "mar"] == qualidade.OK


def test_q2_sem_divergencia(con_carregado):
    assert qualidade.q2_integridade(con_carregado).empty


def test_q2_detecta_divergencia(con, pasta_efd):
    p = pasta_efd / "EFD_ICMS_IPI_22222222000122_202601.txt"
    txt = p.read_bytes().decode("latin-1")
    # remove um C190 sem atualizar o bloco 9
    linhas = txt.split("\r\n")
    i = next(k for k, l in enumerate(linhas) if l.startswith("|C190|"))
    del linhas[i]
    p.write_bytes("\r\n".join(linhas).encode("latin-1"))
    carregar_arquivo(con, p)
    q2 = qualidade.q2_integridade(con)
    regs = set(q2["registro"])
    assert "C190" in regs and "9999" in regs
