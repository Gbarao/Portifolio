import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from './api'
import type { Meta, Options, SavedFilter, SnapshotInfo, UiState } from './types'

const EMPTY_RULES = { op: 'AND' as const, rules: [] }

interface Ctx {
  meta: Meta
  state: UiState
  options: Options | null
  filters: SavedFilter[]
  snaps: SnapshotInfo[]
  dataVersion: number
  set: (patch: Partial<UiState> | ((s: UiState) => Partial<UiState>)) => void
  reloadOptions: () => Promise<void>
  reloadLibrary: () => Promise<void>
  dataChanged: () => void
  applyPreset: (f: SavedFilter) => void
  dimLabel: (k: string) => string
  metricLabel: (k: string) => string
}

const AppCtx = createContext<Ctx>(null as any)
export const useApp = () => useContext(AppCtx)

function normalize(st: Partial<UiState>, meta: Meta): UiState {
  const dims = new Set(meta.dimensions.map((d) => d.key))
  const mets = new Set(meta.metrics.map((m) => m.key))
  const hierarchy = (st.hierarchy || []).filter((d) => dims.has(d))
  const metrics = (st.metrics || []).filter((m) => mets.has(m))
  return {
    gf: st.gf || {},
    rules: (st.rules && (st.rules as any).rules ? st.rules : EMPTY_RULES) as any,
    hierarchy: hierarchy.length ? hierarchy : meta.defaultHierarchy,
    metrics: metrics.length ? metrics : meta.defaultMetrics,
    mode: (['arvore', 'tabela', 'mensal'].includes(st.mode as string) ? st.mode : 'arvore') as any,
    pivotMetric: st.pivotMetric && mets.has(st.pivotMetric) ? st.pivotMetric : 'vl_contabil',
    appliedFilterName: st.appliedFilterName || '',
    page: (['analise', 'arquivos', 'regras', 'auditoria'].includes(st.page as string) ? st.page : 'analise') as any,
  }
}

export function AppProvider({ meta, initial, children }: { meta: Meta; initial: Partial<UiState>; children: ReactNode }) {
  const [state, setState] = useState<UiState>(() => normalize(initial, meta))
  const [options, setOptions] = useState<Options | null>(null)
  const [filters, setFilters] = useState<SavedFilter[]>([])
  const [snaps, setSnaps] = useState<SnapshotInfo[]>([])
  const [dataVersion, setDataVersion] = useState(0)
  const saveTimer = useRef<number>()

  const set = useCallback((patch: Partial<UiState> | ((s: UiState) => Partial<UiState>)) => {
    setState((s) => ({ ...s, ...(typeof patch === 'function' ? patch(s) : patch) }))
  }, [])

  // salvamento automático da sessão (restaurada ao reabrir o programa)
  useEffect(() => {
    window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => { api.put('/api/state', state).catch(() => {}) }, 600)
  }, [state])

  const reloadOptions = useCallback(async () => { setOptions(await api.get('/api/options')) }, [])
  const reloadLibrary = useCallback(async () => {
    const [f, s] = await Promise.all([api.get('/api/filters'), api.get('/api/snapshots')])
    setFilters(f); setSnaps(s)
  }, [])
  useEffect(() => { reloadOptions(); reloadLibrary() }, [reloadOptions, reloadLibrary])

  const dataChanged = useCallback(() => { setDataVersion((v) => v + 1); reloadOptions() }, [reloadOptions])

  const applyPreset = useCallback((f: SavedFilter) => {
    const d = f.definicao || {}
    set((s) => ({
      rules: (d.rules as any) || EMPTY_RULES,
      gf: d.global ?? s.gf,
      hierarchy: d.view?.hierarchy?.length ? d.view.hierarchy : s.hierarchy,
      mode: ({ drill: 'arvore', plana: 'tabela' } as any)[d.view?.mode as string] || (d.view?.mode as any) || s.mode,
      metrics: d.view?.metrics?.length ? d.view.metrics.filter((m) => m !== 'n_docs') : s.metrics,
      appliedFilterName: f.nome,
      page: 'analise',
    }))
  }, [set])

  const dimMap = useMemo(() => Object.fromEntries(meta.dimensions.map((d) => [d.key, d.label])), [meta])
  const metMap = useMemo(() => Object.fromEntries(meta.metrics.map((d) => [d.key, d.label])), [meta])

  const value: Ctx = {
    meta, state, options, filters, snaps, dataVersion, set, reloadOptions, reloadLibrary, dataChanged, applyPreset,
    dimLabel: (k) => dimMap[k] || k, metricLabel: (k) => metMap[k] || k,
  }
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>
}

export function useTheme() {
  const [theme, setTheme] = useState<string>(() => { try { return localStorage.getItem('theme') || 'system' } catch { return 'system' } })
  useEffect(() => {
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.classList.toggle('dark', dark)
    }
    apply()
    try { localStorage.setItem('theme', theme) } catch { /* armazenamento indisponível */ }
    const mq = matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [theme])
  return [theme, setTheme] as const
}
