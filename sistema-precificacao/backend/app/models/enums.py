"""Vocabulario controlado do dominio.

Cada enum abaixo tem origem direta em uma secao da especificacao. Sao
persistidos como texto (``native_enum=False``) para que a evolucao do
vocabulario nao exija ``ALTER TYPE`` em producao.
"""

from __future__ import annotations

from enum import StrEnum


class RegimeTributario(StrEnum):
    """Secao 7.7 -- determina o calculo de `C` e de `r`."""

    LUCRO_REAL = "LUCRO_REAL"
    LUCRO_PRESUMIDO = "LUCRO_PRESUMIDO"
    SIMPLES_NACIONAL = "SIMPLES_NACIONAL"


class StatusDado(StrEnum):
    """Secao 16 -- confiabilidade de cada campo."""

    CONFIRMADO = "CONFIRMADO"
    ESTIMADO = "ESTIMADO"
    PROVISORIO = "PROVISORIO"
    VENCIDO = "VENCIDO"
    INCONSISTENTE = "INCONSISTENTE"


class StatusRegraFiscal(StrEnum):
    """Secao 9.6 -- regra VENCIDA ou BLOQUEADA impede cotacao definitiva."""

    VALIDADA = "VALIDADA"
    PROVISORIA = "PROVISORIA"
    VENCIDA = "VENCIDA"
    BLOQUEADA = "BLOQUEADA"


class CamadaPreco(StrEnum):
    """Secao 8 -- escada de precos. Nenhum preco e apresentado sem rotulo."""

    CAIXA = "CAIXA"
    CONTRIBUICAO = "CONTRIBUICAO"
    OPERACIONAL = "OPERACIONAL"
    SUSTENTAVEL = "SUSTENTAVEL"
    ALVO = "ALVO"
    MERCADO_COMPARAVEL = "MERCADO_COMPARAVEL"


class VisaoCusto(StrEnum):
    """Secao 2 -- as tres visoes reconciliaveis, mantidas simultaneamente."""

    CONTABIL = "CONTABIL"
    GERENCIAL_COMPLETO = "GERENCIAL_COMPLETO"
    RELEVANTE = "RELEVANTE"


class UnidadeMedida(StrEnum):
    KG = "KG"
    TONELADA = "TONELADA"
    FARDO = "FARDO"
    VIAGEM = "VIAGEM"
    SERVICO = "SERVICO"
    METRO_CUBICO = "METRO_CUBICO"
    HORA = "HORA"
    KM = "KM"
    UNIDADE = "UNIDADE"


class TipoMaterial(StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    AMBOS = "AMBOS"


class NaturezaParceiro(StrEnum):
    PESSOA_FISICA = "PESSOA_FISICA"
    PESSOA_JURIDICA = "PESSOA_JURIDICA"
    COOPERATIVA = "COOPERATIVA"
    MEI = "MEI"
    ORGAO_PUBLICO = "ORGAO_PUBLICO"


class PapelParceiro(StrEnum):
    FORNECEDOR = "FORNECEDOR"
    CLIENTE = "CLIENTE"
    AMBOS = "AMBOS"
    TRANSPORTADOR = "TRANSPORTADOR"


class NaturezaCentroCusto(StrEnum):
    PRODUTIVO = "PRODUTIVO"
    APOIO = "APOIO"
    LOGISTICO = "LOGISTICO"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    COMERCIAL = "COMERCIAL"


class Direcionador(StrEnum):
    """Secao 4.1 -- direcionadores com relacao causal com o recurso."""

    NUMERO_RECEBIMENTOS = "NUMERO_RECEBIMENTOS"
    MINUTOS_INSPECAO = "MINUTOS_INSPECAO"
    HORA_EQUIPE = "HORA_EQUIPE"
    HORA_MAO_DE_OBRA = "HORA_MAO_DE_OBRA"
    HORA_MAQUINA = "HORA_MAQUINA"
    HORA_EMPILHADEIRA = "HORA_EMPILHADEIRA"
    HORA_VEICULO = "HORA_VEICULO"
    TONELADA_BRUTA = "TONELADA_BRUTA"
    TONELADA_PROCESSADA = "TONELADA_PROCESSADA"
    TONELADA_EXPEDIDA = "TONELADA_EXPEDIDA"
    TONELADA_DIA = "TONELADA_DIA"
    METRO_QUADRADO_DIA = "METRO_QUADRADO_DIA"
    NUMERO_FARDOS = "NUMERO_FARDOS"
    NUMERO_MOVIMENTOS = "NUMERO_MOVIMENTOS"
    NUMERO_ANALISES = "NUMERO_ANALISES"
    NUMERO_CARREGAMENTOS = "NUMERO_CARREGAMENTOS"
    NUMERO_DOCUMENTOS = "NUMERO_DOCUMENTOS"
    QUILOMETRO = "QUILOMETRO"
    VIAGEM = "VIAGEM"


class TipoEventoProcesso(StrEnum):
    RECEBIMENTO = "RECEBIMENTO"
    PESAGEM = "PESAGEM"
    INSPECAO = "INSPECAO"
    DESCARGA = "DESCARGA"
    TRIAGEM = "TRIAGEM"
    PRENSAGEM = "PRENSAGEM"
    MOAGEM = "MOAGEM"
    LAVAGEM = "LAVAGEM"
    MOVIMENTACAO = "MOVIMENTACAO"
    ARMAZENAGEM = "ARMAZENAGEM"
    CONTROLE_QUALIDADE = "CONTROLE_QUALIDADE"
    EXPEDICAO = "EXPEDICAO"


class TipoPerda(StrEnum):
    """Secao 6.6 -- perda normal integra rendimento; anormal e desvio."""

    PERDA_NORMAL = "PERDA_NORMAL"
    PERDA_ANORMAL = "PERDA_ANORMAL"
    REJEITO = "REJEITO"
    UMIDADE = "UMIDADE"
    DIFERENCA_BALANCA = "DIFERENCA_BALANCA"
    FURTO_AVARIA = "FURTO_AVARIA"
    DETERIORACAO = "DETERIORACAO"
    RECLASSIFICACAO = "RECLASSIFICACAO"
    DESCONTO_COMPRA = "DESCONTO_COMPRA"


class StatusLote(StrEnum):
    ABERTO = "ABERTO"
    EM_PROCESSAMENTO = "EM_PROCESSAMENTO"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    FECHADO = "FECHADO"
    BLOQUEADO = "BLOQUEADO"


class StatusCotacao(StrEnum):
    RASCUNHO = "RASCUNHO"
    SIMULACAO = "SIMULACAO"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    APROVADA = "APROVADA"
    REJEITADA = "REJEITADA"
    EXPIRADA = "EXPIRADA"
    BLOQUEADA = "BLOQUEADA"


class TipoOperacaoFiscal(StrEnum):
    COMPRA = "COMPRA"
    VENDA = "VENDA"
    INDUSTRIALIZACAO = "INDUSTRIALIZACAO"
    SERVICO = "SERVICO"
    BONIFICACAO = "BONIFICACAO"
    DEVOLUCAO = "DEVOLUCAO"
    TRANSFERENCIA = "TRANSFERENCIA"
    FRETE = "FRETE"


class Tributo(StrEnum):
    ICMS = "ICMS"
    ICMS_ST = "ICMS_ST"
    DIFAL = "DIFAL"
    IPI = "IPI"
    PIS = "PIS"
    COFINS = "COFINS"
    ISS = "ISS"
    IRPJ = "IRPJ"
    CSLL = "CSLL"
    INSS_RETENCAO = "INSS_RETENCAO"
    DAS_SIMPLES = "DAS_SIMPLES"
    CBS = "CBS"
    IBS = "IBS"
    IMPOSTO_SELETIVO = "IMPOSTO_SELETIVO"


class TratamentoTributario(StrEnum):
    """Secao 9.2 -- tratamento aplicado pela regra."""

    DEBITO = "DEBITO"
    CREDITO = "CREDITO"
    ISENCAO = "ISENCAO"
    SUSPENSAO = "SUSPENSAO"
    DIFERIMENTO = "DIFERIMENTO"
    SUBSTITUICAO_TRIBUTARIA = "SUBSTITUICAO_TRIBUTARIA"
    RETENCAO = "RETENCAO"
    REDUCAO_BASE = "REDUCAO_BASE"
    NAO_TRIBUTADO = "NAO_TRIBUTADO"
    CREDITO_PRESUMIDO = "CREDITO_PRESUMIDO"


class Recuperabilidade(StrEnum):
    """Secao 9.2 -- credito so reduz custo quando ELEGIVEL e realizavel."""

    ELEGIVEL = "ELEGIVEL"
    VEDADA = "VEDADA"
    PROPORCIONAL = "PROPORCIONAL"
    CONDICIONADA = "CONDICIONADA"
    NAO_APLICAVEL = "NAO_APLICAVEL"


class FormaCalculoBase(StrEnum):
    """Secao 7.6 -- aliquotas nao podem ser somadas sem olhar a base."""

    POR_FORA = "POR_FORA"
    POR_DENTRO = "POR_DENTRO"
    BASE_REDUZIDA = "BASE_REDUZIDA"
    VALOR_FIXO = "VALOR_FIXO"
    PAUTA = "PAUTA"


class AnexoSimples(StrEnum):
    """Secao 9.4 -- Anexo I para comercio, Anexo II para industria."""

    ANEXO_I = "ANEXO_I"
    ANEXO_II = "ANEXO_II"
    ANEXO_III = "ANEXO_III"
    ANEXO_IV = "ANEXO_IV"
    ANEXO_V = "ANEXO_V"


class TipoFrete(StrEnum):
    FROTA_PROPRIA = "FROTA_PROPRIA"
    TERCEIRIZADO = "TERCEIRIZADO"
    CLIENTE_RETIRA = "CLIENTE_RETIRA"
    FORNECEDOR_ENTREGA = "FORNECEDOR_ENTREGA"


class MetodoCustoConjunto(StrEnum):
    """Secao 7.4."""

    MEDICAO_DIRETA = "MEDICAO_DIRETA"
    VRL_RELATIVO = "VRL_RELATIVO"
    QUANTIDADE_FISICA = "QUANTIDADE_FISICA"


class MetodoEstoque(StrEnum):
    CUSTO_MEDIO_PONDERADO = "CUSTO_MEDIO_PONDERADO"
    IDENTIFICACAO_ESPECIFICA = "IDENTIFICACAO_ESPECIFICA"
    PEPS = "PEPS"


class PerfilUsuario(StrEnum):
    """Secao 13.1 -- papeis e segregacao de funcoes."""

    OPERACOES = "OPERACOES"
    LOGISTICA = "LOGISTICA"
    COMPRAS = "COMPRAS"
    COMERCIAL = "COMERCIAL"
    CONTROLADORIA = "CONTROLADORIA"
    FISCAL_CONTABIL = "FISCAL_CONTABIL"
    DIRETORIA = "DIRETORIA"
    TECNOLOGIA = "TECNOLOGIA"


class AcaoAuditoria(StrEnum):
    CRIACAO = "CRIACAO"
    ALTERACAO = "ALTERACAO"
    AJUSTE = "AJUSTE"
    APROVACAO = "APROVACAO"
    REJEICAO = "REJEICAO"
    BLOQUEIO = "BLOQUEIO"
    EXCECAO_APROVADA = "EXCECAO_APROVADA"


class TipoRecurso(StrEnum):
    EMPREGADO = "EMPREGADO"
    EQUIPE = "EQUIPE"
    MAQUINA = "MAQUINA"
    VEICULO = "VEICULO"
    IMOVEL = "IMOVEL"
    AREA = "AREA"
