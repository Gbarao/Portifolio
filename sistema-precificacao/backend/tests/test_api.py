"""Testes de integracao da API.

Sobem a aplicacao inteira sobre um banco SQLite temporario populado pelas
seeds, para exercitar o caminho real: HTTP -> servico -> motor -> banco.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.api.deps import obter_sessao
from app.api.main import criar_app
from app.models import Base, LoteCompra, Material, Parceiro, RegraTributaria, Unidade
from app.seeds.demo import popular

DATA_OPERACAO = date(2026, 3, 10)


@pytest.fixture()
def cliente():
    # Cada conexao nova a um SQLite ":memory:" abre um banco proprio, e o
    # TestClient atende as requisicoes em outra thread. StaticPool mantem uma
    # unica conexao compartilhada, para que a API enxergue as seeds.
    motor = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(motor, "connect")
    def _fk(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(motor)
    Fabrica = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)

    with Fabrica() as sessao:
        popular(sessao)
        sessao.commit()

    def sessao_de_teste():
        sessao = Fabrica()
        try:
            yield sessao
            sessao.commit()
        except Exception:
            sessao.rollback()
            raise
        finally:
            sessao.close()

    app = criar_app()
    app.dependency_overrides[obter_sessao] = sessao_de_teste

    with TestClient(app) as client:
        client.sessao = Fabrica  # type: ignore[attr-defined]
        yield client

    motor.dispose()


def _id_de(cliente, modelo, **filtros):
    with cliente.sessao() as sessao:  # type: ignore[attr-defined]
        consulta = select(modelo)
        for campo, valor in filtros.items():
            consulta = consulta.where(getattr(modelo, campo) == valor)
        return str(sessao.scalars(consulta.limit(1)).one().id)


# --------------------------------------------------------------------------
# Saude e cadastros
# --------------------------------------------------------------------------
def test_saude_responde_com_banco_acessivel(cliente):
    resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "banco": True}


def test_listagem_de_materiais_pagina_e_filtra(cliente):
    resposta = cliente.get("/materiais", params={"familia": "PLASTICO", "limite": 2})
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["limite"] == 2
    assert len(corpo["itens"]) <= 2
    assert all(item["familia"] == "PLASTICO" for item in corpo["itens"])


def test_criar_material_devolve_201_e_persiste(cliente):
    resposta = cliente.post(
        "/materiais",
        json={
            "codigo": "MP-VIDRO",
            "descricao": "Vidro incolor",
            "familia": "VIDRO",
            "tipo": "ENTRADA",
            "rendimento_padrao": "0.82",
        },
    )
    assert resposta.status_code == 201
    assert resposta.json()["codigo"] == "MP-VIDRO"

    assert cliente.get("/materiais/" + resposta.json()["id"]).status_code == 200


def test_material_inexistente_retorna_404_com_corpo_explicativo(cliente):
    resposta = cliente.get("/materiais/00000000-0000-0000-0000-000000000000")
    assert resposta.status_code == 404
    assert resposta.json()["erro"] == "RECURSO_NAO_ENCONTRADO"


def test_parametros_vigentes_dependem_da_data_consultada(cliente):
    unidade_id = _id_de(cliente, Unidade, codigo="MATRIZ-LR")

    vigente = cliente.get(
        f"/unidades/{unidade_id}/parametros", params={"em": "2026-03-10"}
    )
    assert vigente.status_code == 200
    assert vigente.json()["regime_tributario"] == "LUCRO_REAL"

    # Antes do inicio da vigencia nao existe parametro aplicavel.
    anterior = cliente.get(
        f"/unidades/{unidade_id}/parametros", params={"em": "2025-06-01"}
    )
    assert anterior.status_code == 404


# --------------------------------------------------------------------------
# Motor tributario
# --------------------------------------------------------------------------
def test_regra_criada_pela_api_nasce_provisoria(cliente):
    """Nao ha caminho pela API para criar regra ja validada."""

    resposta = cliente.post(
        "/tributario/regras",
        json={
            "codigo": "TESTE-ICMS",
            "descricao": "ICMS de teste",
            "tipo_operacao": "VENDA",
            "tributo": "ICMS",
            "regime_tributario": "LUCRO_REAL",
            "vigencia_inicio": "2026-01-01",
            "fundamento_legal": "Norma de teste",
            "tratamento": "DEBITO",
            "aliquota": "0.18",
            "compoe_deducao_venda": True,
        },
    )
    assert resposta.status_code == 201
    assert resposta.json()["status"] == "PROVISORIA"


def test_validacao_de_regra_registra_autor_e_data(cliente):
    regra_id = _id_de(cliente, RegraTributaria, codigo="LR-VENDA-PIS")

    resposta = cliente.post(
        f"/tributario/regras/{regra_id}/validar",
        json={"validado_por": "Contador responsavel"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "VALIDADA"
    assert corpo["validado_por"] == "Contador responsavel"
    assert corpo["validado_em"] is not None


def test_deducoes_do_lucro_real_somam_pis_e_cofins(cliente):
    resposta = cliente.post(
        "/tributario/deducoes",
        json={
            "contexto": {
                "data_operacao": "2026-03-10",
                "tipo_operacao": "VENDA",
                "regime_tributario": "LUCRO_REAL",
                "uf_origem": "SP",
                "uf_destino": "SP",
            }
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert Decimal(corpo["r_total"]) == Decimal("0.0925")
    assert set(corpo["detalhamento"]) == {"PIS", "COFINS"}
    # As regras das seeds sao provisorias: nao autorizam cotacao definitiva.
    assert corpo["permite_cotacao_definitiva"] is False
    assert corpo["memoria"]["passos"]


def test_deducoes_do_presumido_incluem_presuncao_de_irpj_e_csll(cliente):
    resposta = cliente.post(
        "/tributario/deducoes",
        json={
            "contexto": {
                "data_operacao": "2026-03-10",
                "tipo_operacao": "VENDA",
                "regime_tributario": "LUCRO_PRESUMIDO",
            }
        },
    )
    corpo = resposta.json()

    # 8% x 15% = 1,20% e 12% x 9% = 1,08%.
    assert Decimal(corpo["detalhamento"]["IRPJ"]) == Decimal("0.012")
    assert Decimal(corpo["detalhamento"]["CSLL"]) == Decimal("0.0108")


def test_endpoint_de_mudanca_de_faixa_do_simples_alerta_o_custo_real(cliente):
    resposta = cliente.post(
        "/tributario/simples/mudanca-faixa",
        json={
            "rbt12_atual": "700000",
            "receita_mes_sem_a_venda": "60000",
            "receita_da_venda": "40000",
            "anexo": "ANEXO_II",
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["mudou_de_faixa"] is True
    assert corpo["faixa_antes"] == 3 and corpo["faixa_depois"] == 4
    assert float(corpo["aliquota_marginal_da_venda"]) > float(corpo["aliquota_antes"])
    assert "faixa" in corpo["alerta"].lower()


def test_rbt12_acima_do_teto_retorna_422_e_nao_500(cliente):
    """Erro de premissa e resposta de negocio, nao falha de servidor."""

    resposta = cliente.post(
        "/tributario/simples/aliquota-efetiva",
        json={"rbt12": "9000000", "anexo": "ANEXO_II"},
    )
    assert resposta.status_code == 422
    assert resposta.json()["erro"] == "ParametroInvalidoError"
    assert resposta.json()["bloqueante"] is True


# --------------------------------------------------------------------------
# Operacoes
# --------------------------------------------------------------------------
def test_resultado_do_lote_traz_custos_e_memoria(cliente):
    lote_id = _id_de(cliente, LoteCompra, codigo="LC-2026-000001")

    resposta = cliente.get(f"/lotes/{lote_id}/resultado")
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert Decimal(corpo["balanco"]["quantidade_aceita"]) == Decimal("11600")
    assert Decimal(corpo["balanco"]["rendimento"]) == Decimal("0.9")
    # A perda encarece o kg vendavel em relacao ao kg aceito.
    assert float(corpo["custo_aquisicao_por_kg_vendavel"]) > float(
        corpo["custo_aquisicao_por_kg_aceito"]
    )
    assert corpo["memoria"]["passos"]
    assert any(
        p["formula"].startswith("Rendimento") for p in corpo["memoria"]["passos"]
    )


def test_encerramento_com_massa_aberta_retorna_409(cliente):
    """Regra 1 da secao 11: lote nao encerra com balanco em aberto."""

    lote_id = _id_de(cliente, LoteCompra, codigo="LC-2026-000001")

    # Uma perda extra abre o balanco alem da tolerancia de 2%.
    cliente.post(
        f"/lotes/{lote_id}/perdas",
        json={
            "tipo": "PERDA_ANORMAL",
            "quantidade_kg": "900",
            "causa": "Falha operacional de teste",
            "data_evento": "2026-03-11",
        },
    )

    bloqueado = cliente.post(f"/lotes/{lote_id}/encerrar")
    assert bloqueado.status_code == 409
    assert bloqueado.json()["erro"] == "MassaInconsistenteError"

    # Com justificativa e aprovador, a excecao e aceita e registrada.
    liberado = cliente.post(
        f"/lotes/{lote_id}/encerrar",
        params={
            "justificativa": "Divergencia apurada e aceita pela controladoria",
            "aprovado_por": "Controladoria",
        },
    )
    assert liberado.status_code == 200
    assert liberado.json()["balanco"]["dentro_da_tolerancia"] is False


def test_lote_sem_evento_de_balanca_retorna_422(cliente):
    unidade_id = _id_de(cliente, Unidade, codigo="MATRIZ-LR")
    fornecedor_id = _id_de(cliente, Parceiro, codigo="FOR-COOP-001")
    material_id = _id_de(cliente, Material, codigo="MP-PAPELAO-MISTO")

    criado = cliente.post(
        "/lotes",
        json={
            "codigo": "LC-SEM-BALANCA",
            "unidade_id": unidade_id,
            "fornecedor_id": fornecedor_id,
            "material_id": material_id,
            "data_entrada": "2026-03-15",
            "preco_unitario_bruto": "0.40",
            "quantidade_negociada": "5000",
            "quantidade_negociada_kg": "5000",
        },
    )
    assert criado.status_code == 201

    resposta = cliente.get(f"/lotes/{criado.json()['id']}/resultado")
    assert resposta.status_code == 422
    assert resposta.json()["erro"] == "DadoObrigatorioAusenteError"
    assert "balança" in resposta.json()["mensagem"]


# --------------------------------------------------------------------------
# Cotacoes
# --------------------------------------------------------------------------
def corpo_simulacao(**ajustes):
    base = {
        "contexto": {
            "data_operacao": "2026-03-10",
            "tipo_operacao": "VENDA",
            "regime_tributario": "LUCRO_REAL",
            "uf_origem": "SP",
            "uf_destino": "SP",
        },
        "quantidade_kg": "10000",
        "margem_alvo": "0.12",
        "margem_contribuicao_minima": "0.05",
        "componentes_custo": [
            {"nome": "Aquisicao", "valor": "5000", "camada_minima": "CAIXA"},
            {"nome": "Transformacao", "valor": "800", "camada_minima": "CONTRIBUICAO"},
            {
                "nome": "Estrutura",
                "valor": "1200",
                "camada_minima": "OPERACIONAL",
                "e_desembolso": False,
            },
            {
                "nome": "Administrativas",
                "valor": "900",
                "camada_minima": "SUSTENTAVEL",
                "visoes": ["GERENCIAL_COMPLETO"],
            },
        ],
    }
    base.update(ajustes)
    return base


def test_simulacao_devolve_a_escada_completa_com_finalidades(cliente):
    resposta = cliente.post("/cotacoes/simular", json=corpo_simulacao())
    assert resposta.status_code == 200
    corpo = resposta.json()

    camadas = {p["camada"]: p for p in corpo["precos"]}
    assert {"CAIXA", "CONTRIBUICAO", "OPERACIONAL", "SUSTENTAVEL", "ALVO"} <= set(camadas)
    assert all(p["finalidade"] for p in corpo["precos"])

    precos = [
        float(camadas[c]["preco_unitario"])
        for c in ("CAIXA", "CONTRIBUICAO", "OPERACIONAL", "SUSTENTAVEL", "ALVO")
    ]
    assert precos == sorted(precos), "a escada tem que ser monotonica"


def test_simulacao_avalia_proposta_e_indica_a_alcada(cliente):
    resposta = cliente.post(
        "/cotacoes/simular", json=corpo_simulacao(preco_proposto="0.80")
    )
    avaliacao = resposta.json()["avaliacao_proposta"]

    assert avaliacao is not None
    assert avaliacao["faixa"] in {
        "ENTRE_ALVO_E_SUSTENTAVEL",
        "ENTRE_SUSTENTAVEL_E_CONTRIBUICAO",
    }
    assert avaliacao["alcada_necessaria"]


def test_cotacao_persistida_grava_versao_precos_e_memoria(cliente):
    corpo = corpo_simulacao(
        unidade_id=_id_de(cliente, Unidade, codigo="MATRIZ-LR"),
        cliente_id=_id_de(cliente, Parceiro, codigo="CLI-IND-001"),
        material_id=_id_de(cliente, Material, codigo="PA-PAPELAO-FARDO"),
        criado_por="comercial@exemplo.local",
    )

    criada = cliente.post("/cotacoes", json=corpo)
    assert criada.status_code == 201
    cotacao = criada.json()
    assert cotacao["versao_atual"] == 1
    assert cotacao["calculo"]["memoria"]["passos"]

    from app.models import CotacaoPreco, CotacaoVersao, MemoriaPasso

    with cliente.sessao() as sessao:  # type: ignore[attr-defined]
        versao = sessao.scalars(select(CotacaoVersao)).one()
        precos = sessao.scalars(
            select(CotacaoPreco).where(CotacaoPreco.versao_id == versao.id)
        ).all()
        passos = sessao.scalars(
            select(MemoriaPasso).where(MemoriaPasso.memoria_id == versao.memoria_calculo_id)
        ).all()

    assert len(precos) == 5, "um registro por degrau da escada"
    assert passos, "a memoria foi persistida junto com a versao"
    # As premissas ficaram congeladas no registro.
    assert versao.premissas["margem_alvo"] == "0.12"


def test_nova_versao_preserva_a_anterior(cliente):
    corpo = corpo_simulacao(
        unidade_id=_id_de(cliente, Unidade, codigo="MATRIZ-LR"),
        cliente_id=_id_de(cliente, Parceiro, codigo="CLI-IND-001"),
        material_id=_id_de(cliente, Material, codigo="PA-PAPELAO-FARDO"),
    )
    criada = cliente.post("/cotacoes", json=corpo).json()
    preco_v1 = next(
        p["preco_unitario"] for p in criada["calculo"]["precos"] if p["camada"] == "ALVO"
    )

    revisada = cliente.post(
        f"/cotacoes/{criada['id']}/versoes", json={"margem_alvo": "0.20"}
    )
    assert revisada.status_code == 201
    corpo_revisado = revisada.json()
    preco_v2 = next(
        p["preco_unitario"]
        for p in corpo_revisado["calculo"]["precos"]
        if p["camada"] == "ALVO"
    )

    assert corpo_revisado["versao_atual"] == 2
    assert float(preco_v2) > float(preco_v1)

    from app.models import CotacaoVersao

    with cliente.sessao() as sessao:  # type: ignore[attr-defined]
        versoes = sessao.scalars(
            select(CotacaoVersao).order_by(CotacaoVersao.numero_versao)
        ).all()

    assert [v.numero_versao for v in versoes] == [1, 2]
    assert versoes[0].premissas["margem_alvo"] == "0.12", "versao 1 intacta"


def test_preco_maximo_de_compra_usa_o_r_do_motor_fiscal(cliente):
    resposta = cliente.post(
        "/simulacoes/preco-maximo-compra",
        json={
            "preco_venda_unitario": "0.95",
            "quantidade_vendavel": "9000",
            "quantidade_aceita_esperada": "10000",
            "demais_custos": "2000",
            "margem_alvo": "0.12",
            "contexto": {
                "data_operacao": "2026-03-10",
                "tipo_operacao": "VENDA",
                "regime_tributario": "LUCRO_REAL",
            },
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert Decimal(corpo["deducoes_r"]) == Decimal("0.0925")
    assert float(corpo["preco_maximo_unitario"]) > 0
    assert corpo["memoria"]["passos"]


def test_openapi_documenta_todos_os_modulos(cliente):
    esquema = cliente.get("/openapi.json").json()
    tags = {t["name"] for t in esquema["tags"]}

    assert {"cadastros", "operacoes", "motor tributario", "cotacoes e simulacoes"} <= tags
    assert len(esquema["paths"]) >= 25


# --------------------------------------------------------------------------
# Painel gerencial
# --------------------------------------------------------------------------
def test_painel_agrega_indicadores_do_periodo(cliente):
    resposta = cliente.get("/painel/indicadores")
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["lotes_apurados"] == 1
    assert corpo["lotes_com_erro"] == 0
    assert Decimal(corpo["rendimento_medio"]) == Decimal("0.9")
    assert Decimal(corpo["quantidade_vendavel_kg"]) == Decimal("10440")
    assert Decimal(corpo["custo_total"]) > Decimal("0")


def test_painel_evidencia_ociosidade_por_atividade(cliente):
    """Secao 7.3: a capacidade paga e nao usada aparece separada, no periodo."""

    corpo = cliente.get("/painel/indicadores").json()
    ociosidade = corpo["ociosidade_por_atividade"]

    assert ociosidade, "as atividades apontadas no lote geram ociosidade"
    assert Decimal(corpo["custo_ociosidade_total"]) > Decimal("0")
    # A lista vem da menor ocupacao para a maior: e onde a gestao age primeiro.
    ocupacoes = [Decimal(o["percentual_ocupacao"]) for o in ociosidade]
    assert ocupacoes == sorted(ocupacoes)


def test_painel_declara_o_que_nao_pode_calcular(cliente):
    """Secao 15: dado ausente vira declaracao, nunca zero disfarcado."""

    corpo = cliente.get("/painel/indicadores").json()
    indisponiveis = {i["nome"] for i in corpo["indisponiveis"]}

    assert "Ponte de margem cotada × realizada" in indisponiveis
    assert all(i["motivo"] for i in corpo["indisponiveis"])


def test_painel_separa_credito_condicionado_do_confirmado(cliente):
    corpo = cliente.get("/painel/indicadores").json()

    assert "creditos_confirmados" in corpo
    assert "creditos_condicionados" in corpo


def test_painel_de_periodo_vazio_nao_quebra(cliente):
    """Filtro sem lotes devolve zeros com alerta, nao erro."""

    resposta = cliente.get(
        "/painel/indicadores", params={"de": "2030-01-01", "ate": "2030-12-31"}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["lotes_apurados"] == 0
    assert any("Nenhum lote" in a for a in corpo["alertas"])


def test_painel_ignora_lote_que_nao_apura_sem_derrubar_o_resto(cliente):
    """Um lote sem balanca nao pode zerar o painel inteiro."""

    from app.models import Material as ModeloMaterial

    unidade_id = _id_de(cliente, Unidade, codigo="MATRIZ-LR")
    fornecedor_id = _id_de(cliente, Parceiro, codigo="FOR-COOP-001")
    material_id = _id_de(cliente, ModeloMaterial, codigo="MP-PAPELAO-MISTO")

    cliente.post(
        "/lotes",
        json={
            "codigo": "LC-QUEBRADO",
            "unidade_id": unidade_id,
            "fornecedor_id": fornecedor_id,
            "material_id": material_id,
            "data_entrada": "2026-03-12",
            "preco_unitario_bruto": "0.40",
            "quantidade_negociada": "5000",
            "quantidade_negociada_kg": "5000",
        },
    )

    corpo = cliente.get("/painel/indicadores").json()

    assert corpo["lotes_apurados"] == 1, "o lote bom continua somando"
    assert corpo["lotes_com_erro"] == 1
    assert any("LC-QUEBRADO" in a for a in corpo["alertas"])
