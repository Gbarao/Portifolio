export type ColType = 'money' | 'qty' | 'price' | 'int' | 'pct' | 'text' | 'date' | 'bool'

export interface Table {
  columns: string[]
  types: ColType[]
  rows: any[][]
  totals?: Record<string, any>
  source?: string
  truncated?: boolean
  limit?: number
  ms?: number
  total?: number
}

export interface Dim { key: string; label: string; hasDesc: boolean }
export interface Metric { key: string; label: string; type: string; rowLevel: boolean }
export interface Field { key: string; label: string; type: 'text' | 'number' | 'date' | 'bool' }
export interface Check { key: string; label: string; informative: boolean }

export interface Meta {
  version: string
  native: boolean
  dataDir: string
  exportDir: string
  maxGridRows: number
  workers: number
  cpuCount: number
  tolerancia: number
  dimensions: Dim[]
  metrics: Metric[]
  defaultHierarchy: string[]
  defaultMetrics: string[]
  fields: Field[]
  operators: Record<string, string>
  opsByType: Record<string, string[]>
  checks: Check[]
}

export type Opt = [string, string]
export interface Options {
  filial: Opt[]; fornecedor: Opt[]; cfop: Opt[]; item: Opt[]; uf: Opt[]; ncm: Opt[]; competencias: string[]
}

export interface Rule { id?: string; field: string; operator: string; value: any }
export interface RuleGroup { id?: string; op: 'AND' | 'OR'; rules: (Rule | RuleGroup)[] }

export interface GlobalFilters {
  comp_ini?: string; comp_fim?: string; competencias?: string[]
  filiais?: string[]; ufs_filial?: string[]; fornecedores?: string[]; raizes_fornecedor?: string[]
  busca_fornecedor?: string; cfops?: string[]; cfop_prefixo?: string; itens?: string[]
  busca_item?: string; ncm_prefixo?: string
}

export type Mode = 'arvore' | 'tabela' | 'mensal'
export type Page = 'analise' | 'arquivos' | 'regras' | 'auditoria'

export interface UiState {
  v?: number
  gf: GlobalFilters
  rules: RuleGroup
  hierarchy: string[]
  metrics: string[]
  mode: Mode
  pivotMetric: string
  appliedFilterName: string
  page: Page
}

export interface SavedFilter {
  id: number; nome: string; categoria: string; atualizado_em: string
  definicao: { rules?: RuleGroup; global?: GlobalFilters; view?: { hierarchy?: string[]; mode?: string; metrics?: string[] } }
}
export interface SnapshotInfo { id: number; nome: string; anotacoes: string; criado_em: string; linhas: number; contexto: any }

export interface Job {
  id: string; kind: string; status: 'running' | 'done' | 'error'; msg: string; frac: number
  result: any; error: string | null
}
