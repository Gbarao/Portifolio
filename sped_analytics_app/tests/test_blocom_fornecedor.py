"""Bloco M da EFD-Contribuições (apuração, verificações, conferência com documentos) e busca por fornecedor."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app
from app.database import bloco_m, fornecedor
from app.database.engine import SpedDatabase
from tests import sample_data as sd


def _env(base: Path, patch=None):
    src = base / "src"
    files = sd.write_scenario(src)
    if patch:
        for p in files:
            if p.name.startswith("EFD_CONTRIB") and "2024-01" in p.name:
                txt = p.read_bytes().decode("latin-1")
                p.write_bytes(patch(txt).encode("latin-1"))
    db = SpedDatabase(db_path=base / "t.duckdb", parquet_dir=base / "pq")
    db.import_paths([src], workers=1)
    return db


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    db = _env(tmp_path_factory.mktemp("bm"))
    with TestClient(create_app(db=db)) as c:
        yield {"c": c, "db": db}
    db.close()


def _rows(sec: dict) -> list[dict]:
    return [dict(zip(sec["columns"], r)) for r in sec["rows"]]


# --------------------------------------------------------------------------------------------- Bloco M
def test_visao_geral(env):
    o = env["c"].get("/api/blocom/overview").json()
    assert [e["cnpj"] for e in o["empresas"]] == [sd.CNPJ_A]
    assert o["competencias"] == ["2024-01", "2024-02"] and o["pendentes"] == 0 and o["sem_bloco_m"] == 0


def test_apuracao_e_indicadores(env):
    r = env["c"].post("/api/blocom/query", json={}).json()
    base = sum(sd.BASES_CREDITO.values())
    pis, cof = r["kpis"]["PIS"], r["kpis"]["COFINS"]
    cred_pis = round(base * 0.0165, 2)
    assert pis["creditos_apurados"] == pytest.approx(2 * cred_pis)
    assert pis["contribuicao"] == pytest.approx(2 * sd.RECEITA_BRUTA * 0.0165)
    # jan: 330 - 118,31; fev: 330 - (118,31 + 10 de ajuste) - 50 de crédito anterior (1100)
    assert pis["a_recolher"] == pytest.approx((330 - cred_pis) + (330 - cred_pis - 10 - 50))
    assert pis["creditos_anteriores"] == pytest.approx(50) and cof["creditos_anteriores"] == pytest.approx(200)
    assert pis["saldo_credito"] == pytest.approx(350) and cof["saldo_credito"] == pytest.approx(1400)
    cons = _rows(r["sections"]["consolidacao"])
    assert {(x["competencia"], x["tributo"]) for x in cons} == {(c, t) for c in ("2024-01", "2024-02") for t in ("PIS", "COFINS")}
    # base do crédito por natureza (M105/M505), com descrição da Tabela 4.3.7
    b = [x for x in _rows(r["sections"]["base_credito"]) if x["tributo"] == "PIS" and x["competencia"] == "2024-01"]
    assert {x["nat_bc_cred"]: x["vl_bc_tot"] for x in b} == pytest.approx(sd.BASES_CREDITO)
    assert all(x["nat_desc"] for x in b) and all(x["cod_cred"] == "101" for x in b)
    aj = _rows(r["sections"]["ajustes"])
    assert len(aj) == 2 and {x["tributo"] for x in aj} == {"PIS", "COFINS"} and all(x["competencia"] == "2024-02" for x in aj)
    sal = _rows(r["sections"]["saldo"])
    assert {x["periodo_origem"] for x in sal} == {"2023-12"} and len(sal) == 2
    rec = _rows(r["sections"]["cod_receita"])
    assert {x["cod_rec_desc"] for x in rec} == {"PIS/Pasep não cumulativo", "Cofins não cumulativa"}


def test_verificacoes_e_conferencia_sem_divergencia(env):
    r = env["c"].post("/api/blocom/query", json={}).json()
    ver = _rows(r["sections"]["verificacoes"])
    assert r["divergencias"] == 0 and len(ver) > 20 and all(v["status"] == "OK" for v in ver)
    conf = _rows(r["sections"]["conferencia_resumo"])
    assert len(conf) == 4
    for x in conf:
        assert x["base_docs"] == pytest.approx(sum(sd.BASES_CREDITO.values()))
        assert x["diferenca_base"] == pytest.approx(0) and x["diferenca_credito"] == pytest.approx(0)
    det = _rows(r["sections"]["conferencia"])
    assert all(abs(x["diferenca"]) < 0.005 for x in det)
    # natureza derivada do CFOP só para C170/C191 (revenda e insumo)
    assert {x["nat_bc_cred"] for x in det if x["base_nat_derivada"]} == {"01", "02"}


def test_filtros_por_periodo(env):
    r = env["c"].post("/api/blocom/query", json={"comp_ini": "2024-02", "comp_fim": "2024-02"}).json()
    assert {x["competencia"] for x in _rows(r["sections"]["consolidacao"])} == {"2024-02"}
    assert r["kpis"]["PIS"]["ajustes_credito"] == pytest.approx(10)


def test_divergencias_e_leiaute_anterior(tmp_path):
    def patch(txt: str) -> str:
        # base do crédito de revenda (PIS) informada a menor no M105 e total a recolher errado no M200
        txt = txt.replace("|M105|01|50|2500,00||2500,00|2500,00||||", "|M105|01|50|2400,00||2400,00|2400,00||||", 1)
        old = next(l for l in txt.splitlines() if l.startswith("|M200|"))
        f = old.split("|")
        f[-2] = "1,00"
        txt = txt.replace(old, "|".join(f), 1)
        # M210 no leiaute anterior a 2019 (13 campos)
        m210 = next(l for l in txt.splitlines() if l.startswith("|M210|"))
        g = m210.split("|")
        old_layout = g[:5] + g[8:]     # remove VL_AJUS_ACRES_BC, VL_AJUS_REDUC_BC, VL_BC_CONT_AJUS
        return txt.replace(m210, "|".join(old_layout), 1)

    db = _env(tmp_path, patch)
    try:
        res = bloco_m.analyze(db, {"comp_ini": "2024-01", "comp_fim": "2024-01"})
        conf = res["conferencia"].filter((res["conferencia"]["tributo"] == "PIS") & (res["conferencia"]["nat_bc_cred"] == "01"))
        assert conf["diferenca"].to_list() == [pytest.approx(-100)]
        ver = res["verificacoes"]
        div = ver.filter(ver["status"] == "Divergente")
        assert div.height >= 1 and any("Total a recolher" in v for v in div["verificacao"].to_list())
        cont = res["contribuicao"].filter(res["contribuicao"]["tributo"] == "PIS")
        assert cont["leiaute"].to_list() == ["anterior a 2019"]
        assert cont["vl_cont_per"].to_list() == [pytest.approx(330)] and cont["aliq"].to_list() == [pytest.approx(1.65)]
        assert cont["vl_bc_cont_ajus"].to_list() == [None]
        assert res["leiaute"] == []      # 13 campos é um leiaute conhecido
    finally:
        db.close()


def test_sem_bloco_m(env):
    """Seleção sem nenhuma linha do Bloco M (ex.: escrituração sem apuração) não pode quebrar a tela."""
    r = env["c"].post("/api/blocom/query", json={"empresas": ["00000000000000"]}).json()
    assert r["arquivos"] == 0 and r["divergencias"] == 0
    assert r["kpis"]["PIS"]["a_recolher"] == 0 and all(not s["rows"] for s in r["sections"].values())
    res = bloco_m.analyze(env["db"], {"comp_ini": "2024-01", "comp_fim": "2024-01"})
    assert res["consolidacao"].height == 2


def test_exportacao_bloco_m(env):
    r = env["c"].post("/api/export/blocom", json={}).json()
    assert r["name"].startswith("bloco_m_") and Path(r["path"]).stat().st_size > 5000


# --------------------------------------------------------------------------------------------- fornecedor
def test_busca(env):
    c = env["c"]
    r = c.get("/api/fornecedor/buscar", params={"q": "22.222"}).json()
    assert r["itens"][0]["cnpj_cpf"] == sd.F_X and r["itens"][0]["tem_entradas"]
    r = c.get("/api/fornecedor/buscar", params={"q": "transport"}).json()
    assert [x["cnpj_cpf"] for x in r["itens"]] == [sd.F_T]
    assert c.get("/api/fornecedor/buscar", params={"q": "x"}).json()["itens"] == []


def test_perfil_consolidado(env):
    r = env["c"].post("/api/fornecedor/perfil", json={"cnpjs": ["22.222.222/0001-00"]}).json()
    assert r["cnpjs"] == [sd.F_X]
    # mesmos totais da Análise filtrada pelo fornecedor
    tot = env["c"].post("/api/totals", json={"gf": {"fornecedores": [sd.F_X]}, "metrics": ["vl_contabil", "vl_pis"]}).json()
    assert r["totais"]["vl_contabil"] == pytest.approx(tot["totals"]["vl_contabil"])
    assert r["totais"]["vl_pis"] == pytest.approx(tot["totals"]["vl_pis"])
    assert r["n_docs"] >= 4
    mes = _rows(r["por_mes"])
    assert [x["competencia"] for x in mes] == ["2024-01", "2024-02"]
    assert sum(x["vl_contabil"] for x in mes) == pytest.approx(r["totais"]["vl_contabil"])
    var = _rows(r["variantes"])
    assert {v["arquivos"] for v in var} == {"SPED Fiscal", "EFD-Contribuições"}
    assert len(_rows(r["cadastro"])) == 4 + 4      # 0150 em 4 arquivos do SPED Fiscal + 2 por EFD (2 estabelecimentos)
    assert len(_rows(r["alteracoes"])) == 4        # 0175 nos 4 arquivos do SPED Fiscal


def test_tudo_nos_arquivos_entradas_e_saidas(env):
    c = env["c"]
    regs = c.post("/api/fornecedor/arquivos", json={"cnpjs": [sd.F_Y]}).json()["registros"]
    sf = {r["reg"]: r for r in regs if r["tipo"] == "ICMS_IPI"}
    ec = {r["reg"]: r for r in regs if r["tipo"] == "CONTRIB"}
    # por arquivo do SPED Fiscal: NF2, NF3, NF4 (cancelada) de entrada e NF5 de saída
    assert (sf["C100"]["n"], sf["C100"]["entradas"], sf["C100"]["saidas"]) == (16, 12, 4)
    assert (sf["C170"]["n"], sf["C170"]["entradas"], sf["C170"]["saidas"]) == (8, 4, 4)
    assert (sf["C190"]["n"], sf["C190"]["entradas"], sf["C190"]["saidas"]) == (12, 8, 4)
    assert sf["0150"]["n"] == 4 and "0175" not in sf
    assert ec["C100"]["n"] == 2 and ec["C170"]["n"] == 2 and ec["0150"]["n"] == 2
    # a grade do registro filtrada pelo participante devolve exatamente essas linhas
    q = c.post("/api/raw/ICMS_IPI/query", json={"reg": "C170", "participantes": [sd.F_Y]}).json()
    assert q["total"] == 8 and set(q["rows"][0][q["columns"].index("part_cnpj_cpf")] for _ in [0]) == {sd.F_Y}
    q = c.post("/api/raw/ICMS_IPI/query", json={"reg": "C100", "participantes": [sd.F_Y], "operacao": "1"}).json()
    assert q["total"] == 4
    # C191/C195 trazem o CNPJ do participante no próprio registro
    x = {r["reg"]: r["n"] for r in c.post("/api/fornecedor/arquivos", json={"cnpjs": [sd.F_X]}).json()["registros"]
         if r["tipo"] == "CONTRIB"}
    assert x["C191"] == 2 and x["C195"] == 2
    # período restringe os arquivos
    r1 = c.post("/api/fornecedor/arquivos", json={"cnpjs": [sd.F_Y], "comp_ini": "2024-02"}).json()["registros"]
    assert {r["reg"]: r["n"] for r in r1 if r["tipo"] == "ICMS_IPI"}["C100"] == 8


def test_raiz_e_exportacao(env):
    c = env["c"]
    assert c.post("/api/fornecedor/raiz", json={"raiz": "22222222"}).json()["cnpjs"] == [sd.F_X]
    r = c.post("/api/export/fornecedor", json={"cnpjs": [sd.F_Y]}).json()
    assert Path(r["path"]).stat().st_size > 5000
    assert c.post("/api/fornecedor/perfil", json={"cnpjs": []}).status_code == 400


def test_participante_codigo_por_arquivo(env):
    """O código do participante vale só dentro do arquivo: o mesmo CNPJ pode ter códigos diferentes."""
    db = env["db"]
    sql = fornecedor.participant_lines_sql("ICMS_IPI", [1, 2, 3, 4, 5, 6], "$1")
    n = db.scalar(f"SELECT count(*) FROM {sql} WHERE reg = 'C100'", [[sd.F_T]])
    assert n == 0      # transportadora só tem D100
    assert db.scalar(f"SELECT count(*) FROM {sql} WHERE reg = 'D100'", [[sd.F_T]]) == 4
