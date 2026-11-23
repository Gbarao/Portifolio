import {
  ArrowDownToLine, BadgePercent, Calculator, ChevronsDownUp, Coins, Columns3, Database, FileSpreadsheet, FileText,
  Landmark, ListTree, Receipt, Rows3, Snowflake, Table2, TrendingDown, Wand2, X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { DataGrid, sortRows, tableToGrid, useSort, type GridCol, type GridRow } from '../components/DataGrid'
import { FilterBar, HierarchyEditor, MetricsPicker } from '../components/FilterBar'
import { CollapseToggle, MaxButton, useCollapsed, useMaximize } from '../components/layout'
import { Badge, Button, Dialog, Field, Input, Kpi, Menu, MenuItem, MenuLabel, MenuSep, Popover, Segmented, Select, Tip, cx } from '../components/ui'
import { api, download } from '../lib/api'
import { fmtBRL, fmtCnpj, fmtComp, fmtCompact, fmtInt } from '../lib/format'
import { useApp } from '../lib/store'
import type { ColType, RuleGroup, Table } from '../lib/types'

export type PathItem = [string, any, string]
interface Node { id: string; level: number; path: PathItem[]; code: any; desc?: string; cells: Record<string, any> }
interface Bucket { status: 'loading' | 'done' | 'error'; nodes: Node[]; truncated?: boolean; error?: string }

const CNPJ_DIMS = new Set(['filial', 'fornecedor'])
const KPI_METRICS = ['vl_contabil', 'vl_icms', 'vl_icms_st_fcp', 'vl_ipi', 'vl_pis', 'vl_cofins', 'vl_trib_recuperaveis', 'vl_custo_liquido', 'n_linhas']
const metricType = (t: string): ColType => (({ money: 'money', qty: 'qty', price: 'price', int: 'int' } as any)[t] ?? 'text')

export const hasRules = (r?: RuleGroup | null) => !!r && Array.isArray(r.rules) && r.rules.length > 0

export function codeLabel(dim: string, code: any) {
  if (code == null || code === '') return '(vazio)'
  return CNPJ_DIMS.has(dim) ? fmtCnpj(code) : String(code)
}

export function DimCell({ dim, code, desc }: { dim: string; code: any; desc?: string }) {
  const c = codeLabel(dim, code)
  if (!desc || desc === code) return <span className={cx(code == null && 'italic text-muted')}>{c}</span>
  return (
    <span className="flex min-w-0 items-baseline gap-2">
      <span className="truncate">{desc}</span>
      <span className="num shrink-0 font-mono text-[11.5px] text-muted">{c}</span>
    </span>
  )
}

export function AnalysisPage() {
  const { state, set, meta, dataVersion, dimLabel } = useApp()
  const { hierarchy: h, mode, metrics, pivotMetric } = state
  const rules = hasRules(state.rules) ? state.rules : null
  const base = useMemo(() => ({ gf: state.gf, rules }), [state.gf, rules])
  const queryKey = JSON.stringify({ base, h, mode, metrics, pivotMetric, dataVersion })

  const [kpiCollapsed, setKpiCollapsed] = useCollapsed('analise-kpis')
  const mx = useMaximize()
  // ---------------------------------------------------------------- indicadores
  const [kpi, setKpi] = useState<Record<string, any> | null>(null)
  const [docs, setDocs] = useState<number | null>(null)
  const [trend, setTrend] = useState<Table | null>(null)
  const [info, setInfo] = useState<{ source?: string; ms?: number }>({})
  useEffect(() => {
    let alive = true
    setKpi(null); setDocs(null)
    api.post('/api/totals', { ...base, metrics: KPI_METRICS }).then((r) => alive && setKpi(r.totals)).catch(() => {})
    api.post('/api/aggregate', { ...base, dims: ['competencia'], metrics: ['vl_contabil', 'vl_trib_recuperaveis'], limit: 600, withTotals: false })
      .then((r) => alive && setTrend(r)).catch(() => {})
    // contagem distinta de documentos lê a tabela de itens: chega depois, sem segurar a tela
    const t = setTimeout(() => api.post('/api/count-docs', base).then((r) => alive && setDocs(r.n)).catch(() => {}), 250)
    return () => { alive = false; clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(base), dataVersion])

  // ---------------------------------------------------------------- árvore (carregamento sob demanda)
  const gen = useRef(0)
  const [buckets, setBuckets] = useState<Record<string, Bucket>>({})
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [rootTotals, setRootTotals] = useState<Record<string, any> | null>(null)
  const [pivotCols, setPivotCols] = useState<string[]>([])
  const [flat, setFlat] = useState<Table | null>(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<{ id: string; path: PathItem[] } | null>(null)
  const [sort, toggleSort, setSort] = useSort(null)

  const fetchLevel = useCallback(async (level: number, path: PathItem[], limit?: number) => {
    const dims = [h[level]]
    const p = path.map(([d, v]) => [d, v])
    if (mode === 'mensal') return api.post<Table>('/api/pivot', { ...base, dims, metric: pivotMetric, path: p, limit })
    return api.post<Table>('/api/aggregate', { ...base, dims, metrics, path: p, limit, withTotals: level === 0 })
  }, [base, h, mode, metrics, pivotMetric])

  const toNodes = (t: Table, level: number, parent: Node | null): Node[] => {
    const dim = h[level]
    const ci = t.columns.indexOf(dim), di = t.columns.indexOf(`${dim}__desc`)
    return t.rows.map((r) => {
      const code = r[ci], desc = di >= 0 ? r[di] : undefined
      const cells = Object.fromEntries(t.columns.map((c, j) => [c, r[j]]))
      cells.__dim = desc || (code ?? '')
      const label = desc ? `${codeLabel(dim, code)} ${desc}` : codeLabel(dim, code)
      return {
        id: `${parent?.id ?? ''}\u001f${JSON.stringify(code)}`, level, code, desc,
        path: [...(parent?.path ?? []), [dim, code, label.slice(0, 80)] as PathItem], cells,
      }
    })
  }

  // recarga completa quando filtros/visão mudam
  useEffect(() => {
    const g = ++gen.current
    setBuckets({}); setExpanded(new Set()); setSelected(null); setFlat(null); setLoading(true)
    const t0 = performance.now()
    const run = async () => {
      try {
        if (mode === 'tabela') {
          const t = await api.post<Table>('/api/aggregate', { ...base, dims: h, metrics })
          if (g !== gen.current) return
          setFlat(t); setRootTotals(t.totals ?? null); setInfo({ source: t.source, ms: Math.round(performance.now() - t0) })
        } else {
          setBuckets({ '': { status: 'loading', nodes: [] } })
          const t = await fetchLevel(0, [])
          if (g !== gen.current) return
          if (mode === 'mensal') setPivotCols(t.columns.filter((c) => c !== h[0] && c !== `${h[0]}__desc`))
          setBuckets({ '': { status: 'done', nodes: toNodes(t, 0, null), truncated: t.truncated } })
          setRootTotals(t.totals ?? null); setInfo({ source: t.source, ms: Math.round(performance.now() - t0) })
        }
      } catch (e: any) {
        if (g === gen.current) { setBuckets({ '': { status: 'error', nodes: [], error: e.message } }); toast.error(e.message) }
      } finally {
        if (g === gen.current) setLoading(false)
      }
    }
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey])

  const toggle = useCallback(async (row: GridRow) => {
    const node: Node = row.cells.__node
    if (!node) return
    const isOpen = expanded.has(node.id)
    setExpanded((s) => { const n = new Set(s); isOpen ? n.delete(node.id) : n.add(node.id); return n })
    if (isOpen || buckets[node.id]?.status === 'done' || buckets[node.id]?.status === 'loading') return
    const g = gen.current
    setBuckets((b) => ({ ...b, [node.id]: { status: 'loading', nodes: [] } }))
    try {
      const t = await fetchLevel(node.level + 1, node.path, 2000)
      if (g !== gen.current) return
      setBuckets((b) => ({ ...b, [node.id]: { status: 'done', nodes: toNodes(t, node.level + 1, node), truncated: t.truncated } }))
    } catch (e: any) {
      if (g === gen.current) setBuckets((b) => ({ ...b, [node.id]: { status: 'error', nodes: [], error: e.message } }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, buckets, fetchLevel])

  // ---------------------------------------------------------------- colunas e linhas
  const metricDefs = useMemo(() => Object.fromEntries(meta.metrics.map((m) => [m.key, m])), [meta])
  const treeCol: GridCol = {
    key: '__dim', label: h.map(dimLabel).join(' › '), type: 'text', width: 420, sticky: true,
    render: (r) => { const n: Node = r.cells.__node; return <DimCell dim={h[n.level]} code={n.code} desc={n.desc} /> },
  }
  const valueCols: GridCol[] = mode === 'mensal'
    ? pivotCols.map((c) => ({ key: c, label: c === 'TOTAL' ? 'Total' : fmtComp(c), type: metricType(metricDefs[pivotMetric]?.type ?? 'money'), className: c === 'TOTAL' ? 'font-semibold' : '' }))
    : metrics.map((m) => ({ key: m, label: metricDefs[m]?.label ?? m, type: metricType(metricDefs[m]?.type ?? 'text'), width: m.startsWith('cst') ? 96 : m === 'unid' ? 90 : undefined }))

  const treeRows = useMemo(() => {
    const out: GridRow[] = []
    const walk = (parentId: string, depth: number) => {
      const b = buckets[parentId]
      if (!b) return
      if (b.status === 'loading') { out.push({ id: `${parentId}#loading`, depth, kind: 'loading', cells: {} }); return }
      if (b.status === 'error') { out.push({ id: `${parentId}#err`, depth, kind: 'note', note: `Erro: ${b.error}`, cells: {} }); return }
      const nodes = sortRows(b.nodes, sort)
      for (const n of nodes) {
        const expandable = n.level < h.length - 1
        out.push({ id: n.id, depth, cells: { ...n.cells, __node: n }, expandable, expanded: expanded.has(n.id) })
        if (expandable && expanded.has(n.id)) walk(n.id, depth + 1)
      }
      if (b.truncated) out.push({ id: `${parentId}#more`, depth, kind: 'note', cells: {}, note: `Exibindo os ${b.nodes.length.toLocaleString('pt-BR')} maiores por valor. Refine os filtros ou use Exportar para ver todos.` })
    }
    walk('', 0)
    return out
  }, [buckets, expanded, sort, h.length])

  const flatGrid = useMemo(() => {
    if (!flat) return { columns: [] as GridCol[], rows: [] as GridRow[] }
    const idx = (c: string) => flat.columns.indexOf(c)
    const cols: GridCol[] = h.map((d, i) => ({
      key: d, label: dimLabel(d), type: 'text' as ColType, width: meta.dimensions.find((x) => x.key === d)?.hasDesc ? 280 : 120, sticky: i === 0,
      render: (r: GridRow) => <DimCell dim={d} code={r.cells[d]} desc={r.cells[`${d}__desc`]} />,
    }))
    const rows = flat.rows.map((r, i) => ({ id: String(i), cells: Object.fromEntries(flat.columns.map((c, j) => [c, r[j]])) }))
    void idx
    return { columns: [...cols, ...valueCols], rows: sortRows(rows, sort) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flat, sort, h, metrics])

  const onSelect = (row: GridRow) => {
    if ((row.kind ?? 'row') !== 'row') return
    if (mode === 'tabela') {
      const path: PathItem[] = h.map((d) => [d, row.cells[d], row.cells[`${d}__desc`] ? `${codeLabel(d, row.cells[d])} ${row.cells[`${d}__desc`]}` : codeLabel(d, row.cells[d])])
      setSelected({ id: row.id, path })
    } else {
      const n: Node = row.cells.__node
      setSelected({ id: n.id, path: n.path })
    }
  }

  const rootBucket = buckets['']
  const truncatedFlat = mode === 'tabela' && flat?.truncated

  // ---------------------------------------------------------------- exportação e snapshot
  const [exporting, setExporting] = useState(false)
  const runExport = async (url: string, body: any, label: string) => {
    setExporting(true)
    const id = toast.loading(`Gerando ${label}…`)
    try {
      const r = await api.post(url, body)
      toast.success(`${label} pronto${r.linhas != null ? ` — ${fmtInt(r.linhas)} linhas` : ''}`, {
        id, description: r.path, duration: 9000,
        action: { label: 'Abrir pasta', onClick: () => api.post('/api/open-folder', { path: r.path }) },
      })
      download(r.url)
    } catch (e: any) {
      toast.error(e.message, { id })
    } finally {
      setExporting(false)
    }
  }
  const ctx = { ...base, hierarchy: h, metrics, mode, pivotMetric, appliedFilterName: state.appliedFilterName }
  const [snapOpen, setSnapOpen] = useState(false)

  // ---------------------------------------------------------------- painel de notas
  const [panelH, setPanelH] = useState(300)
  const dragRef = useRef<{ y: number; h: number } | null>(null)
  useEffect(() => {
    const mv = (e: MouseEvent) => { if (dragRef.current) setPanelH(Math.max(140, Math.min(window.innerHeight - 260, dragRef.current.h - (e.clientY - dragRef.current.y)))) }
    const up = () => { dragRef.current = null; document.body.style.cursor = '' }
    window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
  }, [])

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-3 tall:gap-3 tall:p-5">
      {/* filtros */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <FilterBar />
        <div className="flex items-center gap-2 text-[12px] text-muted">
          <CollapseToggle collapsed={kpiCollapsed} onToggle={() => setKpiCollapsed(!kpiCollapsed)} label="indicadores" />
          <MaxButton on={mx.on} onClick={mx.toggle} size="icon-sm" />
          {info.source && (
            <Tip content="Tabela consultada. Resumos pré-somados (agg_*) respondem mais rápido que a tabela de itens (fato).">
              <span className="inline-flex items-center gap-1.5 rounded-md bg-sunken px-2 py-1"><Database className="h-3.5 w-3.5" />{info.source.replace('fato_entradas_consolidadas', 'itens (fato)')}<span className="opacity-60">· {info.ms} ms</span></span>
            </Tip>
          )}
        </div>
      </div>
      <RulesChip />

      {/* indicadores + evolução mensal */}
      {kpiCollapsed ? (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-xl border bg-panel px-3.5 py-2 text-[12.5px] shadow-card">
          {([['Valor contábil', 'vl_contabil'], ['ICMS', 'vl_icms'], ['IPI', 'vl_ipi'], ['PIS', 'vl_pis'], ['COFINS', 'vl_cofins'], ['Recuperáveis', 'vl_trib_recuperaveis'], ['Custo líquido', 'vl_custo_liquido']] as const).map(([l, k]) => (
            <span key={k}><span className="text-muted">{l} </span><b className="num font-semibold">{kpi ? fmtBRL(kpi[k]) : '…'}</b></span>
          ))}
          <span className="text-muted">{docs == null ? '…' : fmtInt(docs)} documentos</span>
        </div>
      ) : (
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_360px]">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Valor contábil" icon={<Receipt className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_contabil)}
            hint={<>{docs == null ? '…' : docs >= 100000 ? fmtCompact(docs) : fmtInt(docs)} documentos · {kpi?.n_linhas >= 100000 ? fmtCompact(kpi?.n_linhas) : fmtInt(kpi?.n_linhas)} linhas</>} />
          <Kpi label="ICMS" icon={<Landmark className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_icms)} />
          <Kpi label="ICMS-ST + FCP" icon={<Landmark className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_icms_st_fcp)} />
          <Kpi label="IPI" icon={<Coins className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_ipi)} />
          <Kpi label="PIS" icon={<BadgePercent className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_pis)} />
          <Kpi label="COFINS" icon={<BadgePercent className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_cofins)} />
          <Kpi label="Tributos recuperáveis" icon={<Calculator className="h-3.5 w-3.5" />} tone="text-ok" loading={!kpi} value={fmtBRL(kpi?.vl_trib_recuperaveis)}
            hint={kpi?.vl_contabil ? `${((kpi.vl_trib_recuperaveis / kpi.vl_contabil) * 100).toFixed(1).replace('.', ',')}% do valor contábil` : undefined} />
          <Kpi label="Custo líquido" icon={<TrendingDown className="h-3.5 w-3.5" />} loading={!kpi} value={fmtBRL(kpi?.vl_custo_liquido)} />
        </div>
        <TrendCard trend={trend} />
      </div>
      )}

      {/* barra de visualização */}
      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={mode} onChange={(m) => { set({ mode: m }); setSort(null) }} options={[
          { value: 'arvore', label: 'Árvore', icon: <ListTree className="h-4 w-4" /> },
          { value: 'tabela', label: 'Tabela', icon: <Table2 className="h-4 w-4" /> },
          { value: 'mensal', label: 'Mês a mês', icon: <Rows3 className="h-4 w-4" /> },
        ]} />
        <HierarchyEditor />
        {mode === 'mensal' && (
          <Select value={pivotMetric} onChange={(e) => set({ pivotMetric: e.target.value })}>
            {meta.metrics.filter((m) => ['money', 'qty', 'int'].includes(m.type) && !m.rowLevel).map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </Select>
        )}
        {mode !== 'mensal' && (
          <Popover trigger={<Button icon={<Columns3 className="h-4 w-4" />}>Colunas <Badge>{metrics.length}</Badge></Button>}>
            <MetricsPicker />
          </Popover>
        )}
        {mode !== 'tabela' && expanded.size > 0 && (
          <Button variant="ghost" icon={<ChevronsDownUp className="h-4 w-4" />} onClick={() => setExpanded(new Set())}>Recolher tudo</Button>
        )}
        <div className="flex-1" />
        <Menu trigger={<Button icon={<ArrowDownToLine className="h-4 w-4" />} loading={exporting}>Exportar</Button>}>
          <MenuLabel>Resumo</MenuLabel>
          <MenuItem icon={<FileSpreadsheet className="h-4 w-4" />} hint="Todos os níveis da hierarquia, com totais e parâmetros"
            onSelect={() => runExport('/api/export/summary', ctx, 'Resumo em Excel')}>Resumo consolidado (Excel)</MenuItem>
          <MenuSep />
          <MenuLabel>Itens detalhados (filtros atuais)</MenuLabel>
          <MenuItem icon={<FileSpreadsheet className="h-4 w-4" />} onSelect={() => runExport('/api/export/lines', { ...ctx, fmt: 'xlsx' }, 'Excel de itens')}>Excel (.xlsx)</MenuItem>
          <MenuItem icon={<FileText className="h-4 w-4" />} hint="Separador ; e vírgula decimal" onSelect={() => runExport('/api/export/lines', { ...ctx, fmt: 'csv' }, 'CSV de itens')}>CSV</MenuItem>
          <MenuItem icon={<Database className="h-4 w-4" />} hint="Para Power BI / Python" onSelect={() => runExport('/api/export/lines', { ...ctx, fmt: 'parquet' }, 'Parquet de itens')}>Parquet</MenuItem>
        </Menu>
        <Button icon={<Snowflake className="h-4 w-4" />} onClick={() => setSnapOpen(true)}>Congelar análise</Button>
      </div>

      {/* grade + painel de notas */}
      <div className="flex min-h-0 flex-1 flex-col">
        {mx.on && <div className="fixed inset-0 z-30 bg-black/30" onClick={mx.toggle} />}
        <div className={cx('min-h-[220px] flex-1', mx.on && 'fixed inset-2 z-40 flex flex-col rounded-xl border bg-bg p-2 shadow-pop')}>
          {mx.on && <div className="flex items-center gap-2 px-1 pb-2 text-[13px] font-semibold">Análise consolidada<span className="font-normal text-muted">· {h.map(dimLabel).join(' › ')}</span><div className="flex-1" /><MaxButton on onClick={mx.toggle} size="icon-sm" /></div>}
          <div className={mx.on ? 'min-h-0 flex-1' : 'h-full'}>
          {mode === 'tabela' ? (
            <DataGrid columns={flatGrid.columns} rows={flatGrid.rows} totals={rootTotals} loading={loading}
              selectedId={selected?.id} onSelect={onSelect} sort={sort} onSort={toggleSort} />
          ) : (
            <DataGrid columns={[treeCol, ...valueCols]} rows={treeRows} totals={rootTotals} loading={loading || rootBucket?.status === 'loading'}
              treeKey="__dim" selectedId={selected?.id} onSelect={onSelect} onToggle={toggle} sort={sort} onSort={toggleSort} />
          )}
          </div>
        </div>
        {truncatedFlat && <div className="pt-1.5 text-[12px] text-warn">Exibindo as {fmtInt(flat?.limit)} maiores linhas por valor; a linha Total considera todas. Use Exportar para o conjunto completo.</div>}

        {selected ? (
          <div className="flex shrink-0 flex-col pt-1" style={{ height: panelH }}>
            <div className="group flex h-3 cursor-row-resize items-center justify-center" onMouseDown={(e) => { dragRef.current = { y: e.clientY, h: panelH }; document.body.style.cursor = 'row-resize' }}>
              <div className="h-1 w-12 rounded-full bg-line group-hover:bg-accent/60" />
            </div>
            <DocsPanel path={selected.path} base={base} ctx={ctx} onClose={() => setSelected(null)} onExport={runExport} />
          </div>
        ) : (
          <div className="pt-2 text-[12px] text-muted">
            Clique em uma linha para ver as notas fiscais que a compõem{mode !== 'tabela' && <> · use <span className="font-medium text-fg/80">▸</span> ou duplo clique para abrir o próximo nível</>}.
          </div>
        )}
      </div>

      <SnapshotDialog open={snapOpen} onOpenChange={setSnapOpen} />
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------
function TrendCard({ trend }: { trend: Table | null }) {
  const data = useMemo(() => {
    if (!trend) return []
    const ci = trend.columns.indexOf('competencia'), vi = trend.columns.indexOf('vl_contabil'), ri = trend.columns.indexOf('vl_trib_recuperaveis')
    return trend.rows.map((r) => ({ c: r[ci] as string, v: Number(r[vi]) || 0, rec: Number(r[ri]) || 0 })).sort((a, b) => a.c.localeCompare(b.c)).slice(-24)
  }, [trend])
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...data.map((d) => d.v))
  const cur = hover != null ? data[hover] : data[data.length - 1]
  return (
    <div className="flex flex-col rounded-xl border bg-panel px-4 py-3 shadow-card">
      <div className="flex items-baseline justify-between">
        <div className="text-[11.5px] font-medium uppercase tracking-wide text-muted">Evolução mensal</div>
        {cur && <div className="text-[12px] text-muted"><span className="font-medium text-fg">{fmtComp(cur.c)}</span> · R$ {fmtCompact(cur.v)} · <span className="text-ok">rec. R$ {fmtCompact(cur.rec)}</span></div>}
      </div>
      <div className="mt-2 flex h-[118px] items-end gap-[3px]" onMouseLeave={() => setHover(null)}>
        {!trend && <div className="skeleton h-full w-full" />}
        {trend && data.length === 0 && <div className="m-auto text-[12px] text-muted">Sem dados</div>}
        {data.map((d, i) => (
          <div key={d.c} className="group relative flex h-full flex-1 cursor-default flex-col items-center justify-end" onMouseEnter={() => setHover(i)}>
            <div className={cx('flex w-full max-w-[34px] flex-col justify-end overflow-hidden rounded-t-[4px] transition-colors', hover === i ? 'bg-accent/80' : 'bg-accent/40')}
              style={{ height: `${Math.max(2, (d.v / max) * 100)}%` }}>
              <div className="w-full bg-ok/75" style={{ height: `${d.v ? Math.min(100, (d.rec / d.v) * 100) : 0}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-muted">
        <span>{data[0] ? fmtComp(data[0].c) : ''}</span>
        <span className="flex items-center gap-3"><span className="flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-accent/60" />Valor contábil</span><span className="flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-ok/70" />Recuperável</span></span>
        <span>{data.length ? fmtComp(data[data.length - 1].c) : ''}</span>
      </div>
    </div>
  )
}

export function RulesChip() {
  const { state, set } = useApp()
  const [desc, setDesc] = useState('')
  const active = hasRules(state.rules)
  useEffect(() => {
    if (!active) { setDesc(''); return }
    api.post('/api/rules/preview', { rules: state.rules }).then((r) => setDesc(r.ok ? r.description : r.error)).catch(() => {})
  }, [JSON.stringify(state.rules), active])
  if (!active) return null
  return (
    <div className="flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/[0.06] px-3 py-1.5 text-[12.5px]">
      <Wand2 className="h-4 w-4 shrink-0 text-accent" />
      <span className="font-medium">{state.appliedFilterName ? `Filtro "${state.appliedFilterName}"` : 'Regras ativas'}:</span>
      <span className="min-w-0 flex-1 truncate text-fg/80">{desc}</span>
      <Button size="sm" variant="ghost" onClick={() => set({ page: 'regras' })}>Editar</Button>
      <Button size="icon-sm" variant="ghost" aria-label="Remover regras" onClick={() => set({ rules: { op: 'AND', rules: [] }, appliedFilterName: '' })}><X className="h-4 w-4" /></Button>
    </div>
  )
}

export function DocsPanel({ path, base, ctx, onClose, onExport }: { path: PathItem[]; base: any; ctx: any; onClose: () => void; onExport: (u: string, b: any, l: string) => void }) {
  const { dimLabel } = useApp()
  const [t, setT] = useState<Table | null>(null)
  const [loading, setLoading] = useState(true)
  const [sort, toggleSort] = useSort(null)
  const p = path.map(([d, v]) => [d, v])
  useEffect(() => {
    let alive = true
    setLoading(true)
    api.post<Table>('/api/documents', { ...base, path: p }).then((r) => { if (alive) { setT(r); setLoading(false) } })
      .catch((e) => { toast.error(e.message); setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(path), JSON.stringify(base)])
  const g = useMemo(() => tableToGrid(t, { sticky: 0, labels: { razao_social_fornecedor: 'Fornecedor', nome_filial: 'Filial' } }), [t])
  const cols = useMemo(() => {
    const order = ['num_doc', 'serie', 'dt_doc', 'dt_e_s', 'razao_social_fornecedor', 'cnpj_cpf_fornecedor', 'cfops', 'vl_contabil', 'vl_icms', 'vl_icms_st_fcp', 'vl_ipi', 'vl_pis', 'vl_cofins', 'qtd', 'linhas', 'status_efd', 'nivel_cruzamento_efd', 'chave', 'cod_mod', 'reg_doc', 'competencia', 'nome_filial', 'cnpj_filial', 'origem']
    const by = Object.fromEntries(g.columns.map((c) => [c.key, c]))
    return order.filter((k) => by[k]).map((k, i) => ({ ...by[k], sticky: i === 0, width: k === 'num_doc' ? 110 : by[k].width }))
  }, [g])
  const totals = useMemo(() => {
    if (!t) return null
    const out: Record<string, number> = {}
    t.columns.forEach((c, j) => { if (['money', 'qty', 'int'].includes(t.types[j])) out[c] = t.rows.reduce((a, r) => a + (Number(r[j]) || 0), 0) })
    return out
  }, [t])
  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-xl border bg-panel shadow-card">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <FileText className="h-4 w-4 text-muted" />
        <div className="min-w-0 flex-1 truncate text-[12.5px]">
          <span className="font-semibold">Notas fiscais</span>
          <span className="text-muted"> · {path.map(([d, , l]) => `${dimLabel(d)}: ${l}`).join('  ›  ')}</span>
        </div>
        {t && <Badge>{fmtInt(t.rows.length)}{t.rows.length >= 5000 ? '+' : ''} documentos</Badge>}
        <Button size="sm" icon={<FileSpreadsheet className="h-3.5 w-3.5" />} onClick={() => onExport('/api/export/documents', { ...ctx, path }, 'Excel de notas')}>Notas</Button>
        <Button size="sm" icon={<FileSpreadsheet className="h-3.5 w-3.5" />} onClick={() => onExport('/api/export/lines', { ...ctx, path, fmt: 'xlsx' }, 'Excel de itens')}>Itens</Button>
        <Button size="icon-sm" variant="ghost" aria-label="Fechar" onClick={onClose}><X className="h-4 w-4" /></Button>
      </div>
      <div className="min-h-0 flex-1 p-2">
        <DataGrid columns={cols} rows={sortRows(g.rows, sort)} totals={totals} loading={loading} rowHeight={32} dense sort={sort} onSort={toggleSort}
          emptyText="Nenhum documento" />
      </div>
    </div>
  )
}

function SnapshotDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { state, reloadLibrary } = useApp()
  const [nome, setNome] = useState('')
  const [notas, setNotas] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (open) { setNome(`Análise ${new Date().toLocaleString('pt-BR').slice(0, 16)}`); setNotas('') } }, [open])
  const save = async () => {
    setBusy(true)
    try {
      const r = await api.post('/api/snapshots', { nome, anotacoes: notas, state })
      toast.success(`Snapshot #${r.id} salvo`, { description: `${fmtInt(r.linhas)} linhas congeladas` })
      onOpenChange(false); reloadLibrary()
    } catch (e: any) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Congelar análise"
      description="Grava um resumo imutável (Parquet somente leitura, com hash de integridade) pela hierarquia completa, com filtros e regras atuais."
      footer={<><Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button><Button variant="primary" loading={busy} onClick={save}>Salvar snapshot</Button></>}>
      <div className="space-y-3">
        <Field label="Nome"><Input value={nome} onChange={(e) => setNome(e.target.value)} /></Field>
        <Field label="Anotações técnicas">
          <textarea value={notas} onChange={(e) => setNotas(e.target.value)} rows={5}
            className="w-full rounded-lg border bg-panel px-3 py-2 text-[13px] focus-ring" placeholder="Contexto, conclusões, pendências…" />
        </Field>
      </div>
    </Dialog>
  )
}
