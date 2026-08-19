/**
 * Tipos da API.
 *
 * Todo valor monetario, quantidade e percentual chega como **string**: a API
 * envia decimais em precisao cheia para preservar a reprodutibilidade da
 * memoria de calculo. A formatacao e responsabilidade do frontend
 * (ver `lib/formato.ts`).
 */

export type Decimal = string;

export interface Pagina<T> {
  itens: T[];
  total: number;
  limite: number;
  deslocamento: number;
}

export type StatusDado =
  | "CONFIRMADO"
  | "ESTIMADO"
  | "PROVISORIO"
  | "VENCIDO"
  | "INCONSISTENTE";

export type StatusRegraFiscal =
  | "VALIDADA"
  | "PROVISORIA"
  | "VENCIDA"
  | "BLOQUEADA";

export type CamadaPreco =
  | "CAIXA"
  | "CONTRIBUICAO"
  | "OPERACIONAL"
  | "SUSTENTAVEL"
  | "ALVO"
  | "MERCADO_COMPARAVEL";

export interface PassoMemoria {
  ordem: number;
  rotulo: string;
  formula: string;
  entradas: Record<string, string>;
  resultado: Decimal;
  unidade: string;
  fonte: string | null;
  vigencia_regra: string | null;
  status_dado: string;
  alerta: string | null;
}

export interface Memoria {
  titulo: string;
  passos: PassoMemoria[];
  alertas: string[];
}

export interface Unidade {
  id: string;
  codigo: string;
  nome: string;
  uf: string;
  municipio: string;
}

export interface Parametro {
  id: string;
  regime_tributario: string;
  anexo_simples: string | null;
  moeda: string;
  taxa_minima_atratividade_anual: Decimal;
  meta_margem_alvo: Decimal;
  meta_margem_contribuicao_minima: Decimal;
  tolerancia_balanco_massa: Decimal;
  horizonte_validade_cotacao_dias: number;
  vigencia_inicio: string;
  vigencia_fim: string | null;
}

export interface Material {
  id: string;
  codigo: string;
  descricao: string;
  familia: string;
  tipo: "ENTRADA" | "SAIDA" | "AMBOS";
  ncm: string | null;
  unidade_padrao: string;
  rendimento_padrao: Decimal | null;
  perda_normal_padrao: Decimal | null;
  umidade_maxima_aceita: Decimal | null;
  contaminacao_maxima_aceita: Decimal | null;
  processo_necessario: string | null;
  status_dado: StatusDado;
  ativo: boolean;
}

export interface Parceiro {
  id: string;
  codigo: string;
  nome: string;
  papel: string;
  natureza: string;
  cnpj_cpf: string | null;
  contribuinte_icms: boolean;
  regime_tributario: string | null;
  uf: string;
  municipio: string;
  prazo_pagamento_dias: number | null;
  prazo_recebimento_dias: number | null;
  inadimplencia_historica: Decimal | null;
  ativo: boolean;
}

export interface Lote {
  id: string;
  codigo: string;
  status: string;
  status_dado: StatusDado;
  data_entrada: string;
  quantidade_negociada_kg: Decimal;
  preco_unitario_bruto: Decimal;
}

export interface Balanco {
  quantidade_bruta: Decimal;
  quantidade_recusada: Decimal;
  quantidade_aceita: Decimal;
  quantidade_vendavel: Decimal;
  quantidade_rejeito: Decimal;
  perda_normal: Decimal;
  perda_anormal: Decimal;
  diferenca_nao_explicada: Decimal;
  rendimento: Decimal;
  taxa_rejeito: Decimal;
  dentro_da_tolerancia: boolean;
}

export interface ResultadoLote {
  lote_id: string;
  codigo: string;
  balanco: Balanco;
  custo_aquisicao_total: Decimal;
  custo_aquisicao_por_kg_aceito: Decimal;
  custo_aquisicao_por_kg_vendavel: Decimal;
  custo_transformacao: Decimal;
  custo_capital: Decimal;
  custo_total: Decimal;
  custo_unitario_vendavel: Decimal;
  creditos_pendentes: Decimal;
  alertas: string[];
  memoria: Memoria;
}

export interface RegraTributaria {
  id: string;
  codigo: string;
  descricao: string;
  tipo_operacao: string;
  tributo: string;
  regime_tributario: string | null;
  vigencia_inicio: string;
  vigencia_fim: string | null;
  fundamento_legal: string;
  aliquota: Decimal | null;
  percentual_presuncao_base: Decimal | null;
  tratamento: string;
  recuperabilidade: string;
  compoe_deducao_venda: boolean;
  gera_credito_compra: boolean;
  incide_sobre_lucro: boolean;
  requer_confirmacao_condicao: boolean;
  condicao_descricao: string | null;
  status: StatusRegraFiscal;
  validado_por: string | null;
  validado_em: string | null;
  versao: number;
}

export interface DegrauPreco {
  camada: CamadaPreco;
  custo_unitario: Decimal;
  deducoes_r: Decimal;
  margem_m: Decimal;
  preco_unitario: Decimal;
  receita_liquida_unitaria: Decimal;
  margem_valor: Decimal;
  margem_percentual: Decimal;
  finalidade: string;
  alerta: string | null;
}

export interface AvaliacaoProposta {
  preco_proposto: Decimal;
  faixa: string;
  alcada_necessaria: string;
  valor_concessao: Decimal;
  bloqueado: boolean;
  mensagem: string;
}

export interface CotacaoCalculada {
  status: string;
  status_fiscal: StatusRegraFiscal;
  permite_cotacao_definitiva: boolean;
  deducoes_r: Decimal;
  detalhamento_r: Record<string, Decimal>;
  quantidade_kg: Decimal;
  custo_por_camada: Record<string, Decimal>;
  precos: DegrauPreco[];
  avaliacao_proposta: AvaliacaoProposta | null;
  alertas: string[];
  memoria: Memoria;
}
