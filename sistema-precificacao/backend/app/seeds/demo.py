"""Dados de demonstracao para desenvolvimento e testes.

AVISO IMPORTANTE
----------------
Nenhum valor deste arquivo e parametro validado da empresa. Aliquotas,
capacidades, rendimentos e custos sao **exemplos** para exercitar o motor de
calculo, e por isso entram no banco com ``status_dado=ESTIMADO`` e
``status=PROVISORIA``. A especificacao (secoes 9.1 e 15) proibe tratar
parametro nao validado como definitivo: enquanto o responsavel fiscal nao
validar cada regra, o sistema deve bloquear cotacao definitiva.

Convencao de unidades e percentuais, valida em todo o sistema:

* peso em quilogramas, distancia em quilometros, tempo em horas, valor em BRL;
* percentuais sao gravados como fracao decimal -- 9,25% e persistido 0.0925.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Atividade,
    AtividadeTaxa,
    CentroCusto,
    ContratoTabela,
    Empresa,
    EmpresaParametro,
    EmpregadoCusto,
    EventoBalanca,
    EventoFrete,
    EventoProcesso,
    EventoQualidade,
    FaixaSimplesNacional,
    ImovelCusto,
    LoteCompra,
    LoteSaida,
    MaquinaCusto,
    Material,
    MaterialSaidaEsperada,
    Parceiro,
    Recurso,
    RegraTributaria,
    RejeitoPerda,
    Unidade,
    Usuario,
    VeiculoCusto,
)
from app.models.enums import (
    AnexoSimples,
    Direcionador,
    FormaCalculoBase,
    MetodoCustoConjunto,
    NaturezaCentroCusto,
    NaturezaParceiro,
    PapelParceiro,
    PerfilUsuario,
    Recuperabilidade,
    RegimeTributario,
    StatusDado,
    StatusLote,
    StatusRegraFiscal,
    TipoEventoProcesso,
    TipoFrete,
    TipoMaterial,
    TipoOperacaoFiscal,
    TipoPerda,
    TipoRecurso,
    TratamentoTributario,
    Tributo,
    UnidadeMedida,
)

D = Decimal
VIGENCIA = date(2026, 1, 1)
OBS_EXEMPLO = "Valor de exemplo para demonstração. Requer validação antes do uso."


# --------------------------------------------------------------------------
# Empresas -- uma por regime, porque o regime e atributo do CNPJ
# --------------------------------------------------------------------------
def _empresa_com_unidade(
    sessao: Session,
    razao: str,
    cnpj: str,
    codigo_unidade: str,
    regime: RegimeTributario,
    anexo: AnexoSimples | None = None,
) -> Unidade:
    empresa = Empresa(razao_social=razao, nome_fantasia=razao, cnpj=cnpj)
    unidade = Unidade(
        empresa=empresa,
        codigo=codigo_unidade,
        nome=f"{razao} - {codigo_unidade}",
        uf="SP",
        municipio="Sorocaba",
        area_total_m2=D("2400"),
    )
    parametro = EmpresaParametro(
        unidade=unidade,
        vigencia_inicio=VIGENCIA,
        regime_tributario=regime,
        anexo_simples=anexo,
        taxa_minima_atratividade_anual=D("0.18"),
        meta_margem_alvo=D("0.12"),
        meta_margem_contribuicao_minima=D("0.05"),
        tolerancia_balanco_massa=D("0.02"),
        tolerancia_reconciliacao_mensal=D("0.01"),
        horizonte_validade_cotacao_dias=7,
        fonte="Seed de demonstracao",
        observacao=OBS_EXEMPLO,
    )
    sessao.add_all([empresa, unidade, parametro])
    return unidade


def criar_empresas(sessao: Session) -> dict[str, Unidade]:
    return {
        "lucro_real": _empresa_com_unidade(
            sessao,
            "Recicla Demonstração Lucro Real Ltda",
            "11111111000191",
            "MATRIZ-LR",
            RegimeTributario.LUCRO_REAL,
        ),
        "lucro_presumido": _empresa_com_unidade(
            sessao,
            "Recicla Demonstração Presumido Ltda",
            "22222222000172",
            "MATRIZ-LP",
            RegimeTributario.LUCRO_PRESUMIDO,
        ),
        "simples": _empresa_com_unidade(
            sessao,
            "Recicla Demonstração Simples ME",
            "33333333000153",
            "MATRIZ-SN",
            RegimeTributario.SIMPLES_NACIONAL,
            AnexoSimples.ANEXO_II,
        ),
    }


# --------------------------------------------------------------------------
# Materiais
# --------------------------------------------------------------------------
def criar_materiais(sessao: Session) -> dict[str, Material]:
    papelao = Material(
        codigo="MP-PAPELAO-MISTO",
        descricao="Papelão misto recebido solto",
        familia="PAPEL",
        tipo=TipoMaterial.ENTRADA,
        ncm="47071000",
        umidade_referencia=D("0.10"),
        umidade_maxima_aceita=D("0.18"),
        contaminacao_maxima_aceita=D("0.05"),
        rendimento_padrao=D("0.90"),
        perda_normal_padrao=D("0.04"),
        processo_necessario="Triagem e prensagem",
        status_dado=StatusDado.ESTIMADO,
    )
    papelao_fardo = Material(
        codigo="PA-PAPELAO-FARDO",
        descricao="Papelão enfardado tipo aparas marrom",
        familia="PAPEL",
        tipo=TipoMaterial.SAIDA,
        ncm="47071000",
        densidade_kg_m3=D("450"),
        status_dado=StatusDado.ESTIMADO,
    )
    pet_misto = Material(
        codigo="MP-PET-MISTO",
        descricao="PET pós-consumo misto",
        familia="PLASTICO",
        tipo=TipoMaterial.ENTRADA,
        ncm="39159000",
        rendimento_padrao=D("0.85"),
        perda_normal_padrao=D("0.06"),
        processo_necessario="Triagem por cor e prensagem",
        status_dado=StatusDado.ESTIMADO,
    )
    pet_cristal = Material(
        codigo="PA-PET-CRISTAL",
        descricao="PET cristal prensado",
        familia="PLASTICO",
        tipo=TipoMaterial.SAIDA,
        ncm="39159000",
        status_dado=StatusDado.ESTIMADO,
    )
    pet_colorido = Material(
        codigo="PA-PET-COLORIDO",
        descricao="PET colorido prensado",
        familia="PLASTICO",
        tipo=TipoMaterial.SAIDA,
        ncm="39159000",
        status_dado=StatusDado.ESTIMADO,
    )
    filme = Material(
        codigo="PA-FILME-PEBD",
        descricao="Filme PEBD prensado",
        familia="PLASTICO",
        tipo=TipoMaterial.SAIDA,
        ncm="39151000",
        status_dado=StatusDado.ESTIMADO,
    )
    sessao.add_all([papelao, papelao_fardo, pet_misto, pet_cristal, pet_colorido, filme])

    # Mix esperado de saida -- alimenta o custo-padrao e o rateio de custo
    # conjunto quando a triagem gera mais de um produto (secao 7.4).
    sessao.add_all(
        [
            MaterialSaidaEsperada(
                material_entrada=papelao,
                material_saida=papelao_fardo,
                rendimento_padrao=D("0.90"),
                metodo_custo_conjunto=MetodoCustoConjunto.MEDICAO_DIRETA,
            ),
            MaterialSaidaEsperada(
                material_entrada=pet_misto,
                material_saida=pet_cristal,
                rendimento_padrao=D("0.55"),
                gastos_posteriores_estimados_kg=D("0.05"),
            ),
            MaterialSaidaEsperada(
                material_entrada=pet_misto,
                material_saida=pet_colorido,
                rendimento_padrao=D("0.30"),
                gastos_posteriores_estimados_kg=D("0.04"),
            ),
        ]
    )
    return {
        "papelao": papelao,
        "papelao_fardo": papelao_fardo,
        "pet_misto": pet_misto,
        "pet_cristal": pet_cristal,
        "pet_colorido": pet_colorido,
        "filme": filme,
    }


# --------------------------------------------------------------------------
# Parceiros
# --------------------------------------------------------------------------
def criar_parceiros(sessao: Session, materiais: dict[str, Material]) -> dict[str, Parceiro]:
    cooperativa = Parceiro(
        codigo="FOR-COOP-001",
        nome="Cooperativa de Catadores Demonstração",
        papel=PapelParceiro.FORNECEDOR,
        natureza=NaturezaParceiro.COOPERATIVA,
        cnpj_cpf="44444444000134",
        contribuinte_icms=False,
        regime_tributario=RegimeTributario.SIMPLES_NACIONAL,
        uf="SP",
        municipio="Sorocaba",
        prazo_pagamento_dias=7,
        indice_qualidade=D("0.88"),
        indice_pontualidade=D("0.92"),
    )
    sucateiro = Parceiro(
        codigo="FOR-PJ-002",
        nome="Aparas e Sucatas Demonstração Ltda",
        papel=PapelParceiro.FORNECEDOR,
        natureza=NaturezaParceiro.PESSOA_JURIDICA,
        cnpj_cpf="55555555000115",
        inscricao_estadual="111.222.333.444",
        contribuinte_icms=True,
        regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
        uf="SP",
        municipio="Itu",
        prazo_pagamento_dias=14,
        indice_qualidade=D("0.94"),
        indice_pontualidade=D("0.85"),
    )
    industria = Parceiro(
        codigo="CLI-IND-001",
        nome="Indústria de Papel Demonstração S.A.",
        papel=PapelParceiro.CLIENTE,
        natureza=NaturezaParceiro.PESSOA_JURIDICA,
        cnpj_cpf="66666666000196",
        inscricao_estadual="222.333.444.555",
        contribuinte_icms=True,
        # Cliente no lucro real: chave da isencao prevista na Lei 15.394/2026.
        regime_tributario=RegimeTributario.LUCRO_REAL,
        uf="SP",
        municipio="Limeira",
        prazo_recebimento_dias=30,
        limite_credito=D("500000"),
        inadimplencia_historica=D("0.008"),
        concentracao_receita=D("0.35"),
    )
    transportador = Parceiro(
        codigo="TRA-001",
        nome="Transportes Demonstração Ltda",
        papel=PapelParceiro.TRANSPORTADOR,
        natureza=NaturezaParceiro.PESSOA_JURIDICA,
        cnpj_cpf="77777777000177",
        contribuinte_icms=True,
        regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
        uf="SP",
        municipio="Sorocaba",
    )
    sessao.add_all([cooperativa, sucateiro, industria, transportador])

    sessao.add(
        ContratoTabela(
            parceiro=industria,
            material=materiais["papelao_fardo"],
            vigencia_inicio=VIGENCIA,
            preco_unitario=D("0.95"),
            unidade_comercial=UnidadeMedida.KG,
            indexador="Indice de aparas marrom",
            faixa_qualidade="Umidade ate 12%, impureza ate 3%",
            tolerancia_peso=D("0.01"),
            prazo_pagamento_dias=30,
            tipo_frete=TipoFrete.FROTA_PROPRIA,
            quantidade_minima_kg=D("20000"),
            status_dado=StatusDado.ESTIMADO,
            observacao=OBS_EXEMPLO,
        )
    )
    return {
        "cooperativa": cooperativa,
        "sucateiro": sucateiro,
        "industria": industria,
        "transportador": transportador,
    }


# --------------------------------------------------------------------------
# Estrutura de custos: centros, recursos, fichas e taxas de atividade
# --------------------------------------------------------------------------
def criar_estrutura_custos(sessao: Session, unidade: Unidade) -> dict[str, Any]:
    centros = {
        codigo: CentroCusto(
            unidade=unidade,
            codigo=codigo,
            nome=nome,
            natureza=natureza,
            responsavel="Responsável de demonstração",
        )
        for codigo, nome, natureza in [
            ("CC-REC", "Recebimento e pesagem", NaturezaCentroCusto.PRODUTIVO),
            ("CC-TRI", "Triagem", NaturezaCentroCusto.PRODUTIVO),
            ("CC-PRE", "Prensagem", NaturezaCentroCusto.PRODUTIVO),
            ("CC-ARM", "Armazenagem", NaturezaCentroCusto.APOIO),
            ("CC-FRO", "Frota", NaturezaCentroCusto.LOGISTICO),
            ("CC-ADM", "Administrativo", NaturezaCentroCusto.ADMINISTRATIVO),
            ("CC-COM", "Comercial", NaturezaCentroCusto.COMERCIAL),
        ]
    }
    sessao.add_all(centros.values())
    # Flush para materializar os UUIDs antes de referencia-los por id.
    sessao.flush()

    triador = Recurso(
        unidade=unidade,
        centro_custo=centros["CC-TRI"],
        tipo=TipoRecurso.EMPREGADO,
        codigo="EMP-TRI-001",
        nome="Triador",
        capacidade_teorica_mes=D("176"),
        capacidade_pratica_mes=D("150"),
        unidade_capacidade="HORA",
    )
    prensa = Recurso(
        unidade=unidade,
        centro_custo=centros["CC-PRE"],
        tipo=TipoRecurso.MAQUINA,
        codigo="MAQ-PRE-001",
        nome="Prensa enfardadeira horizontal",
        capacidade_teorica_mes=D("352"),
        capacidade_pratica_mes=D("280"),
        unidade_capacidade="HORA_MAQUINA",
    )
    caminhao = Recurso(
        unidade=unidade,
        centro_custo=centros["CC-FRO"],
        tipo=TipoRecurso.VEICULO,
        codigo="VEI-001",
        nome="Caminhão truck carga seca",
        capacidade_teorica_mes=D("9000"),
        capacidade_pratica_mes=D("7000"),
        unidade_capacidade="KM",
    )
    galpao = Recurso(
        unidade=unidade,
        centro_custo=centros["CC-ARM"],
        tipo=TipoRecurso.IMOVEL,
        codigo="IMO-001",
        nome="Galpão industrial",
        capacidade_teorica_mes=D("2400"),
        capacidade_pratica_mes=D("1800"),
        unidade_capacidade="M2",
    )
    sessao.add_all([triador, prensa, caminhao, galpao])

    # Ficha de custo por componentes -- sem multiplicador universal (secao 6.2).
    sessao.add(
        EmpregadoCusto(
            recurso=triador,
            funcao="Triador",
            centro_custo_id=centros["CC-TRI"].id,
            vigencia_inicio=VIGENCIA,
            salario_base=D("2200"),
            adicionais=D("180"),
            horas_extras_media=D("120"),
            encargos_patronais=D("620"),
            fgts=D("200"),
            beneficios=D("480"),
            provisao_ferias_e_adicional=D("245"),
            provisao_decimo_terceiro=D("183"),
            provisao_rescisao=D("90"),
            epi_uniforme_exames=D("60"),
            treinamento=D("25"),
            # 176 horas pagas, 150 produtivas praticas: a diferenca cobre
            # ferias, feriados, pausas e ociosidade normal (secao 6.2).
            horas_pagas_mes=D("176"),
            horas_produtivas_praticas_mes=D("150"),
            status_dado=StatusDado.ESTIMADO,
            observacao=OBS_EXEMPLO,
        )
    )
    sessao.add(
        MaquinaCusto(
            recurso=prensa,
            vigencia_inicio=VIGENCIA,
            depreciacao_mensal=D("3800"),
            custo_capital_mensal=D("1200"),
            manutencao_preventiva_mensal=D("900"),
            seguro_mensal=D("250"),
            outros_fixos_mensal=D("150"),
            energia_kwh_por_hora=D("22"),
            custo_energia_por_kwh=D("0.78"),
            consumiveis_por_hora=D("3.50"),
            manutencao_variavel_por_hora=D("6.00"),
            horas_teoricas_mes=D("352"),
            horas_praticas_mes=D("280"),
            disponibilidade=D("0.92"),
            status_dado=StatusDado.ESTIMADO,
            observacao=OBS_EXEMPLO,
        )
    )
    sessao.add(
        VeiculoCusto(
            recurso=caminhao,
            vigencia_inicio=VIGENCIA,
            placa="ABC1D23",
            capacidade_util_kg=D("14000"),
            depreciacao_ou_arrendamento_mensal=D("6500"),
            seguro_mensal=D("900"),
            licenciamento_mensal=D("180"),
            rastreamento_mensal=D("120"),
            pessoal_fixo_mensal=D("6800"),
            custo_capital_mensal=D("1500"),
            combustivel_por_km=D("1.85"),
            pneus_por_km=D("0.22"),
            manutencao_variavel_por_km=D("0.38"),
            lubrificantes_consumiveis_por_km=D("0.07"),
            custo_por_hora_operacao=D("18.00"),
            km_praticos_mes=D("7000"),
            horas_praticas_mes=D("176"),
            status_dado=StatusDado.ESTIMADO,
            observacao=OBS_EXEMPLO,
        )
    )
    sessao.add(
        ImovelCusto(
            recurso=galpao,
            vigencia_inicio=VIGENCIA,
            aluguel_mensal=D("18000"),
            iptu_mensal=D("1400"),
            vigilancia_mensal=D("2600"),
            seguro_mensal=D("700"),
            limpeza_mensal=D("1800"),
            manutencao_predial_mensal=D("900"),
            utilidades_mensal=D("2100"),
            licencas_ambientais_mensal=D("450"),
            area_total_m2=D("2400"),
            area_produtiva_m2=D("1500"),
            area_armazenagem_m2=D("700"),
            status_dado=StatusDado.ESTIMADO,
        )
    )

    # Atividades do ABC. A taxa e sempre pool / capacidade PRATICA: a
    # ociosidade fica evidenciada no periodo, nunca embutida na taxa.
    definicoes = [
        ("ATV-REC", "Recebimento e pesagem", TipoEventoProcesso.RECEBIMENTO,
         Direcionador.NUMERO_RECEBIMENTOS, "recebimento", "CC-REC", "4800", "120"),
        ("ATV-TRI", "Triagem manual", TipoEventoProcesso.TRIAGEM,
         Direcionador.HORA_MAO_DE_OBRA, "hora", "CC-TRI", "27600", "1200"),
        ("ATV-PRE", "Prensagem e enfardamento", TipoEventoProcesso.PRENSAGEM,
         Direcionador.HORA_MAQUINA, "hora-maquina", "CC-PRE", "6300", "280"),
        ("ATV-ARM", "Armazenagem", TipoEventoProcesso.ARMAZENAGEM,
         Direcionador.TONELADA_DIA, "tonelada-dia", "CC-ARM", "12400", "9000"),
        ("ATV-EXP", "Expedição e carregamento", TipoEventoProcesso.EXPEDICAO,
         Direcionador.NUMERO_CARREGAMENTOS, "carregamento", "CC-REC", "3600", "45"),
    ]
    atividades: dict[str, Atividade] = {}
    for codigo, nome, tipo_evento, direcionador, unidade_dir, cc, pool, capacidade in definicoes:
        atividade = Atividade(
            unidade=unidade,
            centro_custo=centros[cc],
            codigo=codigo,
            nome=nome,
            tipo_evento=tipo_evento,
            direcionador=direcionador,
            unidade_direcionador=unidade_dir,
            justificativa_direcionador="Direcionador causal definido na secao 4.1.",
        )
        pool_valor = D(pool)
        capacidade_valor = D(capacidade)
        sessao.add(atividade)
        sessao.add(
            AtividadeTaxa(
                atividade=atividade,
                vigencia_inicio=VIGENCIA,
                pool_custo_mensal=pool_valor,
                capacidade_pratica_direcionador=capacidade_valor,
                taxa=pool_valor / capacidade_valor,
                status_dado=StatusDado.ESTIMADO,
                memoria_composicao=(
                    f"taxa = pool {pool_valor} / capacidade pratica {capacidade_valor}"
                ),
                observacao=OBS_EXEMPLO,
            )
        )
        atividades[codigo] = atividade

    return {"centros": centros, "atividades": atividades,
            "recursos": {"triador": triador, "prensa": prensa,
                         "caminhao": caminhao, "galpao": galpao}}


# --------------------------------------------------------------------------
# Matriz tributaria (secao 9.4) -- uma regra por combinacao, nunca um
# percentual unico. Todas nascem PROVISORIA: so o responsavel fiscal promove
# para VALIDADA, e antes disso a cotacao definitiva fica bloqueada.
# --------------------------------------------------------------------------
def construir_regras_tributarias() -> list[RegraTributaria]:
    """Monta as regras sem persistir -- reutilizavel fora do banco."""

    def regra(**campos: Any) -> RegraTributaria:
        campos.setdefault("vigencia_inicio", VIGENCIA)
        campos.setdefault("status", StatusRegraFiscal.PROVISORIA)
        campos.setdefault("observacao", OBS_EXEMPLO)
        return RegraTributaria(**campos)

    regras = [
        # ---------------- A) Lucro Real ----------------
        # Lei 15.394/2026: credito de PIS/Cofins na aquisicao de residuos e
        # aparas por PJ do lucro real que os use como materia-prima. E regra
        # CONDICIONAL -- `requer_confirmacao_condicao` impede que o credito
        # reduza o custo antes de a condicao ser confirmada.
        regra(
            codigo="LR-COMPRA-PIS-CREDITO",
            descricao="Credito de PIS/Pasep na aquisicao de residuos e aparas",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.COMPRA,
            tributo=Tributo.PIS,
            familia_material=None,
            aliquota=D("0.0165"),
            forma_calculo_base=FormaCalculoBase.POR_FORA,
            tratamento=TratamentoTributario.CREDITO,
            recuperabilidade=Recuperabilidade.CONDICIONADA,
            percentual_recuperavel=D("1"),
            prazo_realizacao_credito_dias=60,
            gera_credito_compra=True,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "Adquirente no lucro real e material utilizado como materia-prima "
                "ou material secundario, conforme Lei 15.394/2026."
            ),
            fundamento_legal="Lei n. 15.394, de 22 de abril de 2026.",
        ),
        regra(
            codigo="LR-COMPRA-COFINS-CREDITO",
            descricao="Credito de Cofins na aquisicao de residuos e aparas",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.COMPRA,
            tributo=Tributo.COFINS,
            aliquota=D("0.076"),
            tratamento=TratamentoTributario.CREDITO,
            recuperabilidade=Recuperabilidade.CONDICIONADA,
            percentual_recuperavel=D("1"),
            prazo_realizacao_credito_dias=60,
            gera_credito_compra=True,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "Adquirente no lucro real e material utilizado como materia-prima "
                "ou material secundario, conforme Lei 15.394/2026."
            ),
            fundamento_legal="Lei n. 15.394, de 22 de abril de 2026.",
        ),
        regra(
            codigo="LR-VENDA-PIS",
            descricao="PIS nao cumulativo sobre a receita de venda",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.PIS,
            aliquota=D("0.0165"),
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=True,
            fundamento_legal="Legislacao do PIS nao cumulativo. Validar aplicacao.",
        ),
        regra(
            codigo="LR-VENDA-COFINS",
            descricao="Cofins nao cumulativa sobre a receita de venda",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.COFINS,
            aliquota=D("0.076"),
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=True,
            fundamento_legal="Legislacao da Cofins nao cumulativa. Validar aplicacao.",
        ),
        # Isencao prevista na Lei 15.394/2026 para venda a PJ do lucro real:
        # a chave e o regime do CLIENTE, nao o da empresa vendedora.
        regra(
            codigo="LR-VENDA-ISENCAO-15394",
            descricao="Isencao de PIS/Cofins na venda de residuos a PJ do lucro real",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.PIS,
            regime_parceiro=RegimeTributario.LUCRO_REAL,
            aliquota=D("0"),
            tratamento=TratamentoTributario.ISENCAO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=False,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "Destinatario pessoa juridica no lucro real e item abrangido pela lei."
            ),
            fundamento_legal="Lei n. 15.394, de 22 de abril de 2026.",
        ),
        # IRPJ/CSLL do lucro real incidem sobre o lucro apurado no periodo:
        # ficam FORA de `r` e a margem-alvo e pre-tributo (secao 7.7-A).
        regra(
            codigo="LR-IRPJ-LUCRO",
            descricao="IRPJ sobre o lucro real apurado no periodo",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.IRPJ,
            aliquota=D("0.15"),
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=False,
            incide_sobre_lucro=True,
            fundamento_legal="Apuracao do lucro real. Nao integra a variavel r.",
        ),
        regra(
            codigo="LR-CSLL-LUCRO",
            descricao="CSLL sobre o lucro real apurado no periodo",
            regime_tributario=RegimeTributario.LUCRO_REAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.CSLL,
            aliquota=D("0.09"),
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=False,
            incide_sobre_lucro=True,
            fundamento_legal="Apuracao do lucro real. Nao integra a variavel r.",
        ),
        # ---------------- B) Lucro Presumido ----------------
        regra(
            codigo="LP-COMPRA-SEM-CREDITO",
            descricao="Aquisicao sem direito a credito no regime cumulativo",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.COMPRA,
            tributo=Tributo.PIS,
            aliquota=D("0"),
            tratamento=TratamentoTributario.NAO_TRIBUTADO,
            recuperabilidade=Recuperabilidade.VEDADA,
            gera_credito_compra=False,
            compoe_custo_nao_recuperavel=True,
            fundamento_legal=(
                "Regime cumulativo: tributo embutido na compra nao gera credito."
            ),
        ),
        regra(
            codigo="LP-VENDA-PIS",
            descricao="PIS cumulativo sobre a receita bruta",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.PIS,
            aliquota=D("0.0065"),
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
            fundamento_legal="Regime cumulativo do PIS. Validar aplicacao.",
        ),
        regra(
            codigo="LP-VENDA-COFINS",
            descricao="Cofins cumulativa sobre a receita bruta",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.COFINS,
            aliquota=D("0.03"),
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
            fundamento_legal="Regime cumulativo da Cofins. Validar aplicacao.",
        ),
        # No presumido o IRPJ/CSLL viram percentual linear sobre a receita
        # bruta e, por isso, integram `r` (secao 7.7-B).
        # Efeito em r = presuncao x aliquota (ex.: 8% x 15% = 1,2%).
        regra(
            codigo="LP-VENDA-IRPJ-PRESUMIDO",
            descricao="IRPJ por presuncao sobre a receita bruta de mercadorias",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.IRPJ,
            percentual_presuncao_base=D("0.08"),
            aliquota=D("0.15"),
            forma_calculo_base=FormaCalculoBase.BASE_REDUZIDA,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
            incide_sobre_lucro=False,
            fundamento_legal=(
                "Presuncao de 8% para venda de mercadorias. Adicional de 10% sobre "
                "o excedente deve ser avaliado separadamente."
            ),
        ),
        regra(
            codigo="LP-VENDA-CSLL-PRESUMIDO",
            descricao="CSLL por presuncao sobre a receita bruta de mercadorias",
            regime_tributario=RegimeTributario.LUCRO_PRESUMIDO,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.CSLL,
            percentual_presuncao_base=D("0.12"),
            aliquota=D("0.09"),
            forma_calculo_base=FormaCalculoBase.BASE_REDUZIDA,
            tratamento=TratamentoTributario.DEBITO,
            compoe_deducao_venda=True,
            incide_sobre_lucro=False,
            fundamento_legal="Presuncao de 12% para venda de mercadorias.",
        ),
        # ---------------- C) Simples Nacional ----------------
        regra(
            codigo="SN-COMPRA-SEM-CREDITO",
            descricao="Aquisicao sem apropriacao de qualquer credito tributario",
            regime_tributario=RegimeTributario.SIMPLES_NACIONAL,
            tipo_operacao=TipoOperacaoFiscal.COMPRA,
            tributo=Tributo.ICMS,
            aliquota=D("0"),
            tratamento=TratamentoTributario.NAO_TRIBUTADO,
            recuperabilidade=Recuperabilidade.VEDADA,
            gera_credito_compra=False,
            compoe_custo_nao_recuperavel=True,
            fundamento_legal=(
                "Simples Nacional: valor bruto da nota, frete e seguro compoem o "
                "custo liquido, sem credito."
            ),
        ),
        # A aliquota do DAS nao e fixa: vem da faixa de RBT12 vigente.
        # Por isso `aliquota` fica nula e o motor a resolve em tempo de calculo.
        regra(
            codigo="SN-VENDA-DAS",
            descricao="DAS pela aliquota efetiva da faixa de RBT12",
            regime_tributario=RegimeTributario.SIMPLES_NACIONAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.DAS_SIMPLES,
            aliquota=None,
            forma_calculo_base=FormaCalculoBase.POR_DENTRO,
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=True,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "Aliquota efetiva calculada sobre a RBT12 do periodo. Venda volumosa "
                "pode mudar de faixa e elevar o DAS de todo o faturamento do mes."
            ),
            fundamento_legal="Lei Complementar n. 123/2006, Anexos I e II.",
        ),
        # Segregacao do ICMS de dentro do DAS quando houver isencao ou
        # diferimento estadual sobre sucata (secao 9.4-3).
        regra(
            codigo="SN-VENDA-ICMS-DIFERIDO",
            descricao="Segregacao do ICMS do DAS por diferimento estadual em sucata",
            regime_tributario=RegimeTributario.SIMPLES_NACIONAL,
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.ICMS,
            uf_origem="SP",
            uf_destino="SP",
            aliquota=D("0"),
            tratamento=TratamentoTributario.DIFERIMENTO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=False,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "Operacao interna com sucata amparada por diferimento estadual: "
                "a parcela de ICMS deve ser segregada do DAS."
            ),
            fundamento_legal="Legislacao estadual de diferimento de sucata. Validar.",
        ),
        # ---------------- Transicao CBS/IBS (secao 9.5) ----------------
        regra(
            codigo="GERAL-VENDA-CBS-2026",
            descricao="CBS destacada no ano de teste de 2026",
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.CBS,
            aliquota=D("0.009"),
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            # Ano de teste: destacado no documento, sem efeito de caixa.
            compoe_deducao_venda=False,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "2026 e ano de teste: valor destacado no documento fiscal, com "
                "dispensa de recolhimento nas condicoes informadas pela Receita."
            ),
            fundamento_legal="Lei Complementar n. 214/2025 e orientacoes para 2026.",
        ),
        regra(
            codigo="GERAL-VENDA-IBS-2026",
            descricao="IBS destacado no ano de teste de 2026",
            tipo_operacao=TipoOperacaoFiscal.VENDA,
            tributo=Tributo.IBS,
            aliquota=D("0.001"),
            tratamento=TratamentoTributario.DEBITO,
            recuperabilidade=Recuperabilidade.NAO_APLICAVEL,
            compoe_deducao_venda=False,
            requer_confirmacao_condicao=True,
            condicao_descricao=(
                "2026 e ano de teste: valor destacado no documento fiscal, com "
                "dispensa de recolhimento nas condicoes informadas pela Receita."
            ),
            fundamento_legal="Lei Complementar n. 214/2025 e orientacoes para 2026.",
        ),
    ]
    return regras


def criar_regras_tributarias(sessao: Session) -> list[RegraTributaria]:
    regras = construir_regras_tributarias()
    sessao.add_all(regras)
    return regras


def construir_faixas_simples() -> list[FaixaSimplesNacional]:
    """Faixas dos Anexos I e II.

    A aliquota efetiva nunca e a nominal:
    ``efetiva = (RBT12 x nominal - parcela_deduzir) / RBT12``.
    A reparticao permite segregar o ICMS quando houver isencao ou diferimento
    estadual, evitando pagamento indevido dentro do recolhimento unificado.
    """

    # anexo, faixa, rbt12_ini, rbt12_fim, nominal, deduzir,
    # (irpj, csll, cofins, pis, cpp, icms, ipi)
    linhas = [
        (AnexoSimples.ANEXO_I, 1, "0", "180000", "0.040", "0",
         ("0.055", "0.035", "0.1274", "0.0276", "0.415", "0.34", "0")),
        (AnexoSimples.ANEXO_I, 2, "180000.01", "360000", "0.073", "5940",
         ("0.055", "0.035", "0.1274", "0.0276", "0.415", "0.34", "0")),
        (AnexoSimples.ANEXO_I, 3, "360000.01", "720000", "0.095", "13860",
         ("0.055", "0.035", "0.1274", "0.0276", "0.42", "0.335", "0")),
        (AnexoSimples.ANEXO_I, 4, "720000.01", "1800000", "0.107", "22500",
         ("0.055", "0.035", "0.1274", "0.0276", "0.42", "0.335", "0")),
        (AnexoSimples.ANEXO_I, 5, "1800000.01", "3600000", "0.143", "87300",
         ("0.055", "0.035", "0.1274", "0.0276", "0.42", "0.335", "0")),
        (AnexoSimples.ANEXO_I, 6, "3600000.01", "4800000", "0.19", "378000",
         ("0.135", "0.10", "0.2827", "0.0613", "0.421", "0", "0")),
        (AnexoSimples.ANEXO_II, 1, "0", "180000", "0.045", "0",
         ("0.055", "0.035", "0.1151", "0.0249", "0.375", "0.32", "0.075")),
        (AnexoSimples.ANEXO_II, 2, "180000.01", "360000", "0.078", "5940",
         ("0.055", "0.035", "0.1151", "0.0249", "0.375", "0.32", "0.075")),
        (AnexoSimples.ANEXO_II, 3, "360000.01", "720000", "0.10", "13860",
         ("0.055", "0.035", "0.1151", "0.0249", "0.375", "0.32", "0.075")),
        (AnexoSimples.ANEXO_II, 4, "720000.01", "1800000", "0.112", "22500",
         ("0.055", "0.035", "0.1151", "0.0249", "0.375", "0.32", "0.075")),
        (AnexoSimples.ANEXO_II, 5, "1800000.01", "3600000", "0.147", "85500",
         ("0.055", "0.035", "0.1151", "0.0249", "0.375", "0.32", "0.075")),
        (AnexoSimples.ANEXO_II, 6, "3600000.01", "4800000", "0.30", "720000",
         ("0.085", "0.075", "0.2096", "0.0454", "0.235", "0", "0.35")),
    ]
    faixas = [
        FaixaSimplesNacional(
            anexo=anexo,
            ordem_faixa=ordem,
            rbt12_inicio=D(inicio),
            rbt12_fim=D(fim),
            aliquota_nominal=D(nominal),
            parcela_deduzir=D(deduzir),
            percentual_irpj=D(reparticao[0]),
            percentual_csll=D(reparticao[1]),
            percentual_cofins=D(reparticao[2]),
            percentual_pis=D(reparticao[3]),
            percentual_cpp=D(reparticao[4]),
            percentual_icms=D(reparticao[5]),
            percentual_ipi=D(reparticao[6]),
            vigencia_inicio=VIGENCIA,
            status=StatusRegraFiscal.PROVISORIA,
            fundamento_legal=(
                "Lei Complementar n. 123/2006. Conferir tabela vigente com o "
                "responsavel fiscal antes de promover para VALIDADA."
            ),
        )
        for anexo, ordem, inicio, fim, nominal, deduzir, reparticao in linhas
    ]
    return faixas


def criar_faixas_simples(sessao: Session) -> list[FaixaSimplesNacional]:
    faixas = construir_faixas_simples()
    sessao.add_all(faixas)
    return faixas


# --------------------------------------------------------------------------
# Lote de exemplo com balanco de massa fechado
# --------------------------------------------------------------------------
def criar_lote_exemplo(
    sessao: Session,
    unidade: Unidade,
    materiais: dict[str, Material],
    parceiros: dict[str, Parceiro],
    estrutura: dict[str, Any],
) -> LoteCompra:
    """Lote didatico do papelao: 12.000 kg recebidos, 11.600 aceitos.

    Balanco de massa (secao 7.1), fechado exatamente:
        aceita 11.600 = vendavel 10.440 + rejeito 800 + perda normal 360
        rendimento = 10.440 / 11.600 = 90%
    """

    data_entrada = date(2026, 3, 10)
    lote = LoteCompra(
        codigo="LC-2026-000001",
        unidade=unidade,
        fornecedor_id=parceiros["cooperativa"].id,
        material_id=materiais["papelao"].id,
        documento_modelo="55",
        documento_numero="000012345",
        cfop="1102",
        data_entrada=data_entrada,
        data_competencia=data_entrada,
        data_caixa=data_entrada + timedelta(days=7),
        preco_unitario_bruto=D("0.42"),
        unidade_negociada=UnidadeMedida.KG,
        quantidade_negociada=D("12000"),
        quantidade_negociada_kg=D("12000"),
        frete_entrada=D("380"),
        pedagio_entrada=D("42"),
        coleta_carga_descarga=D("120"),
        pesagem_inspecao=D("35"),
        destinacao_rejeito_estimada=D("96"),
        tipo_frete_entrada=TipoFrete.FROTA_PROPRIA,
        prazo_pagamento_dias=7,
        status=StatusLote.EM_PROCESSAMENTO,
        status_dado=StatusDado.ESTIMADO,
        observacao=OBS_EXEMPLO,
    )
    sessao.add(lote)
    sessao.flush()

    sessao.add(
        EventoBalanca(
            lote_id=lote.id,
            momento="ENTRADA",
            peso_bruto_kg=D("15500"),
            tara_kg=D("3500"),
            peso_liquido_kg=D("12000"),
            identificacao_balanca="BAL-01",
            operador="Operador de demonstração",
            data_hora=datetime(2026, 3, 10, 8, 30),
        )
    )
    sessao.add(
        EventoQualidade(
            lote_id=lote.id,
            amostra="AM-001",
            umidade_percentual=D("0.14"),
            impureza_percentual=D("0.035"),
            classificacao="Marrom tipo B",
            # 400 kg recusados fisicamente reduzem a quantidade aceita.
            quantidade_recusada_kg=D("400"),
            desconto_aplicado=D("168"),
            responsavel="Inspetor de demonstração",
            data_hora=datetime(2026, 3, 10, 9, 15),
        )
    )

    atividades = estrutura["atividades"]
    centros = estrutura["centros"]
    recursos = estrutura["recursos"]
    consumos = [
        (atividades["ATV-REC"], None, TipoEventoProcesso.RECEBIMENTO, "CC-REC", D("1"), 8, 9),
        (atividades["ATV-TRI"], recursos["triador"], TipoEventoProcesso.TRIAGEM, "CC-TRI", D("6"), 10, 16),
        (atividades["ATV-PRE"], recursos["prensa"], TipoEventoProcesso.PRENSAGEM, "CC-PRE", D("2.5"), 16, 18),
        (atividades["ATV-ARM"], None, TipoEventoProcesso.ARMAZENAGEM, "CC-ARM", D("52.2"), 18, 18),
    ]
    for atividade, recurso, tipo_evento, cc, quantidade, hora_ini, hora_fim in consumos:
        sessao.add(
            EventoProcesso(
                lote_id=lote.id,
                atividade_id=atividade.id,
                recurso_id=recurso.id if recurso is not None else None,
                centro_custo_id=centros[cc].id,
                tipo_evento=tipo_evento,
                inicio=datetime(2026, 3, 10, hora_ini, 0),
                fim=datetime(2026, 3, 10, hora_fim, 0),
                quantidade_direcionador=quantidade,
                quantidade_processada_kg=D("11600"),
                consumo_energia_kwh=D("55") if tipo_evento == TipoEventoProcesso.PRENSAGEM else None,
            )
        )

    saida = LoteSaida(
        codigo="LS-2026-000001",
        lote_origem_id=lote.id,
        material_id=materiais["papelao_fardo"].id,
        quantidade_kg=D("10440"),
        numero_fardos=22,
        qualidade="Marrom tipo B",
        umidade_percentual=D("0.11"),
        preco_estimado_venda_kg=D("0.95"),
        metodo_custo_conjunto=MetodoCustoConjunto.MEDICAO_DIRETA,
        data_producao=date(2026, 3, 11),
        status=StatusLote.ABERTO,
        status_dado=StatusDado.ESTIMADO,
    )
    sessao.add(saida)
    sessao.add_all(
        [
            RejeitoPerda(
                lote_id=lote.id,
                tipo=TipoPerda.REJEITO,
                quantidade_kg=D("800"),
                integra_custo_padrao=True,
                destino="Aterro licenciado",
                custo_destinacao=D("96"),
                causa="Material não reciclável misturado ao lote",
                data_evento=date(2026, 3, 11),
            ),
            RejeitoPerda(
                lote_id=lote.id,
                tipo=TipoPerda.PERDA_NORMAL,
                quantidade_kg=D("360"),
                integra_custo_padrao=True,
                causa="Umidade e finos do processo de triagem",
                data_evento=date(2026, 3, 11),
            ),
        ]
    )
    sessao.add(
        EventoFrete(
            unidade_id=unidade.id,
            lote_compra_id=lote.id,
            tipo_frete=TipoFrete.FROTA_PROPRIA,
            recurso_veiculo_id=recursos["caminhao"].id,
            origem="Cooperativa — Sorocaba/SP",
            destino="Galpão — Sorocaba/SP",
            km_carregado=D("38"),
            # Retorno vazio entra no custo da viagem (caso de teste 6).
            km_vazio=D("38"),
            horas_totais=D("4"),
            horas_espera=D("1"),
            carga_util_kg=D("12000"),
            ocupacao=D("0.857"),
            pedagio=D("42"),
            data_viagem=date(2026, 3, 10),
        )
    )
    return lote


def criar_usuarios(sessao: Session, unidade: Unidade) -> None:
    sessao.add_all(
        [
            Usuario(
                nome="Operação Demonstração",
                email="operacao@exemplo.local",
                perfil=PerfilUsuario.OPERACOES,
                unidade_id=unidade.id,
            ),
            Usuario(
                nome="Controladoria Demonstração",
                email="controladoria@exemplo.local",
                perfil=PerfilUsuario.CONTROLADORIA,
                unidade_id=unidade.id,
                alcada_valor=D("20000"),
                pode_ver_dados_salariais=True,
            ),
            Usuario(
                nome="Fiscal Demonstração",
                email="fiscal@exemplo.local",
                perfil=PerfilUsuario.FISCAL_CONTABIL,
                unidade_id=unidade.id,
            ),
            Usuario(
                nome="Comercial Demonstração",
                email="comercial@exemplo.local",
                perfil=PerfilUsuario.COMERCIAL,
                unidade_id=unidade.id,
                alcada_valor=D("5000"),
            ),
        ]
    )


def popular(sessao: Session) -> dict[str, Any]:
    """Popula a base de demonstracao inteira e devolve as referencias criadas."""

    unidades = criar_empresas(sessao)
    sessao.flush()

    materiais = criar_materiais(sessao)
    parceiros = criar_parceiros(sessao, materiais)
    sessao.flush()

    unidade_principal = unidades["lucro_real"]
    estrutura = criar_estrutura_custos(sessao, unidade_principal)
    sessao.flush()

    regras = criar_regras_tributarias(sessao)
    faixas = criar_faixas_simples(sessao)
    criar_usuarios(sessao, unidade_principal)
    sessao.flush()

    lote = criar_lote_exemplo(sessao, unidade_principal, materiais, parceiros, estrutura)
    sessao.flush()

    return {
        "unidades": unidades,
        "materiais": materiais,
        "parceiros": parceiros,
        "estrutura": estrutura,
        "regras": regras,
        "faixas": faixas,
        "lote": lote,
    }


def main() -> None:  # pragma: no cover - utilitario de linha de comando
    from app.db.session import SessionLocal, engine
    from app.models import Base

    Base.metadata.create_all(engine)
    with SessionLocal() as sessao:
        dados = popular(sessao)
        sessao.commit()
        print(f"Base de demonstracao populada em {engine.url}")
        print(f"  unidades ............ {len(dados['unidades'])}")
        print(f"  materiais ........... {len(dados['materiais'])}")
        print(f"  regras tributarias .. {len(dados['regras'])} (todas PROVISORIA)")
        print(f"  faixas do Simples ... {len(dados['faixas'])}")
        print(f"  lote de exemplo ..... {dados['lote'].codigo}")


if __name__ == "__main__":  # pragma: no cover
    main()
