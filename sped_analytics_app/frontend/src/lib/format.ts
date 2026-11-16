import type { ColType } from './types'

const money = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const qty = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 })
const price = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
const int = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })

export const fmtMoney = (v: any) => (v == null || v === '' ? '' : money.format(Number(v)))
export const fmtBRL = (v: any) => (v == null ? '—' : 'R$ ' + money.format(Number(v)))
export const fmtInt = (v: any) => (v == null ? '' : int.format(Number(v)))
export const fmtCompact = (v: any) => (v == null ? '—' : compact.format(Number(v)))

export function fmtCnpj(v: any): string {
  const s = v == null ? '' : String(v)
  if (/^\d{14}$/.test(s)) return s.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')
  if (/^\d{11}$/.test(s)) return s.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4')
  return s
}

export function fmtDate(v: any): string {
  if (!v) return ''
  const s = String(v)
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(.*)$/)
  return m ? `${m[3]}/${m[2]}/${m[1]}${m[4] || ''}` : s
}

export function fmtComp(v: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(v || '')
  if (!m) return v
  const meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
  return `${meses[Number(m[2]) - 1]}/${m[1].slice(2)}`
}

export function fmtCell(v: any, t: ColType, col?: string): string {
  if (v == null || v === '') return ''
  switch (t) {
    case 'money': return money.format(Number(v))
    case 'qty': return qty.format(Number(v))
    case 'price': return price.format(Number(v))
    case 'int': return int.format(Number(v))
    case 'pct': return qty.format(Number(v)) + '%'
    case 'date': return fmtDate(v)
    case 'bool': return v ? 'Sim' : 'Não'
    default:
      if (col && /cnpj|fornecedor$|filial$/.test(col)) return fmtCnpj(v)
      return String(v)
  }
}

export const isNumeric = (t: ColType) => ['money', 'qty', 'price', 'int', 'pct'].includes(t)

export const COLUMN_LABELS: Record<string, string> = {
  competencia: 'Competência', cnpj_filial: 'CNPJ Filial', nome_filial: 'Filial', reg_doc: 'Registro', cod_mod: 'Modelo',
  num_doc: 'Número', serie: 'Série', dt_doc: 'Emissão', dt_e_s: 'Entrada', chave: 'Chave', cnpj_cpf_fornecedor: 'CNPJ Fornecedor',
  razao_social_fornecedor: 'Fornecedor', cfops: 'CFOPs', linhas: 'Linhas', qtd: 'Quantidade', vl_item: 'Valor Itens',
  vl_contabil: 'Valor Contábil', vl_icms: 'ICMS', vl_icms_st_fcp: 'ICMS-ST + FCP', vl_ipi: 'IPI', vl_pis: 'PIS',
  vl_cofins: 'COFINS', status_efd: 'Status EFD', nivel_cruzamento_efd: 'Nível de Cruzamento', origem: 'Origem',
  id_arquivo: 'ID', tipo_sped: 'Tipo', cnpj: 'CNPJ', nome: 'Nome', finalidade: 'Finalidade', documentos: 'Docs.',
  tamanho_mb: 'MB', data_importacao: 'Importado em', ativo: 'Ativo', substituido_por: 'Substituído por',
  caminho_origem: 'Caminho', data: 'Data', acao: 'Ação', arquivo: 'Arquivo', mensagem: 'Mensagem', num_item: 'Item nº',
  cod_item: 'Código Item', descr_item: 'Descrição', cfop: 'CFOP', cst_icms: 'CST ICMS', cst_pis: 'CST PIS',
  cst_cofins: 'CST COFINS', cst_ipi: 'CST IPI', vl_bc_pis: 'BC PIS', vl_bc_cofins: 'BC COFINS', tipo_item: 'Tipo Item',
  aliq_icms: 'Alíq. ICMS', comp_efd: 'Competência EFD', nivel: 'Nível', pct_linhas: '% Linhas', pct_pis: '% PIS',
  pis_efd: 'PIS na EFD', pis_totalizador: 'PIS no Totalizador', dif_pis: 'Dif. PIS', cofins_efd: 'COFINS na EFD',
  cofins_totalizador: 'COFINS no Totalizador', dif_cofins: 'Dif. COFINS', dif_bc_pis: 'Dif. BC PIS',
  dif_bc_cofins: 'Dif. BC COFINS', vl_doc_sf: 'Valor Doc. SF', vl_doc_efd: 'Valor Doc. EFD', dif_vl_doc: 'Dif. Doc.',
  vl_merc_sf: 'Mercadoria SF', vl_merc_efd: 'Mercadoria EFD', dif_vl_merc: 'Dif. Mercadoria', cod_item_sf: 'Item SF',
  cod_item_efd: 'Item EFD', cfop_sf: 'CFOP SF', cfop_efd: 'CFOP EFD', qtd_sf: 'Qtd SF', qtd_efd: 'Qtd EFD',
  vl_item_sf: 'Valor Item SF', vl_item_efd: 'Valor Item EFD', dif_vl_item: 'Dif. Item', cod_item_unificado: 'Item',
  vl_doc: 'Valor Doc.', TOTAL: 'Total',
}
