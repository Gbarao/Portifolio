import {
  ArrowDownToLine, ArrowDownWideNarrow, ArrowUpNarrowWide, BookmarkPlus, Columns3, Database, Filter,
  GripVertical, LayoutTemplate, Plus, Rows3, Search, ShieldCheck, Sigma, Trash2, X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { DataGrid, type GridCol, type GridRow } from '../components/DataGrid'
import { FilterBar } from '../components/FilterBar'
import { CollapseToggle, MaxButton, SidePanel, useCollapsed, useDragHeight, useMaximize } from '../components/layout'
import { Badge, Button, Card, Dialog, Field, Input, Menu, MenuItem, MenuLabel, MenuSep, Popover, Select, Switch, Tip, cx } from '../components/ui'
import { api, download } from '../lib/api'
import { fmtComp, fmtInt } from '../lib/format'
import { DEFAULT_REPORT, useApp } from '../lib/store'
import type { ColType, Having, ReportLayout, ReportState } from '../lib/types'
import { DimCell, DocsPanel, RulesChip, codeLabel, hasRules, type PathItem } from './AnalysisPage'

interface ReportResp {
  columns: string[]; types: ColType[]; rows: any[][]; totals: Record<string, any>
  columnsMeta: { key: string; group: string; metric: string }[]
  truncated: boolean; rowCount: number | null; source: string; metrics: string[]
  sort: { by: string; dir: 'asc' | 'desc' }; labels: Record<string, string>; ms: number
}

const SEP = '␟'
const ADDITIVE_T = new Set(['money', 'qty', 'int'])
const PRESETS: ReportLayout[] = [
  { nome: 'Unidade › Fornecedor › CFOP › Descrição do item (valores e tributos)', rows: ['filial', 'fornecedor', 'cfop', 'descr_item'], col: null,
    metrics: ['vl_contabil', 'vl_icms', 'vl_icms_st_fcp', 'vl_ipi', 'vl_pis', 'vl_cofins', 'vl_trib_recuperaveis', 'vl_custo_liquido'] },
  { nome: 'Fornecedor › Descrição do item (quantidade e preço médio)', rows: ['fornecedor', 'descr_item'], col: null,
    metrics: ['qtd', 'unid', 'preco_medio', 'vl_contabil', 'vl_custo_liquido'] },
  { nome: 'CFOP mês a mês (valor contábil)', rows: ['cfop'], col: 'competencia', metrics: ['vl_contabil'] },
  { nome: 'Unidade mês a mês (ICMS, PIS e COFINS)', rows: ['filial'], col: 'competencia', metrics: ['vl_icms', 'vl_pis', 'vl_cofins'] },
  { nome: 'Unidade › CST PIS (bases e créditos)', rows: ['filial', 'cst_pis'], col: null, metrics: ['vl_contabil', 'vl_bc_pis', 'vl_pis', 'vl_bc_cofins', 'vl_cofins'] },
  { nome: 'Fornecedor por status na EFD-Contribuições', rows: ['fornecedor'], col: 'status_efd', metrics: ['vl_contabil'] },
]
const LIMITS = [50, 100, 500, 1000, 5000, 20000]
const HAVING_OPS: Record<string, string> = { '>': 'maior que', '>=': 'maior ou igual a', '<': 'menor que', '<=': 'menor ou igual a', '=': 'igual a', '!=': 'diferente de', zero: 'igual a zero', nao_zero: 'diferente de zero' }

type Drag = { kind: 'dim' | 'metric'; key: string; from?: 'rows' | 'col' | 'metrics'; index?: number }

export function ReportPage() {
  const { state, set, meta, dataVersion, dimLabel, metricLabel } = useApp()
  const rp: ReportState = state.report ?? DEFAULT_REPORT
  const upd = (p: Partial<ReportState>) => set((s) => ({ report: { ...s.report, ...p } }))
  const rules = hasRules(state.rules) ? state.rules : null
  const base = useMemo(() => ({ gf: state.gf, rules }), [state.gf, rules])
  const metricDefs = useMemo(() => Object.fromEntries(meta.metrics.map((m) => [m.key, m])), [meta])

  // texto com debounce
  const [texto, setTexto] = useState(rp.texto)
  useEffect(() => { setTexto(rp.texto) }, [rp.texto])
  useEffect(() => { const t = setTimeout(() => { if (texto !== rp.texto) upd({ texto }) }, 400); return () => clearTimeout(t) }, [texto]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------- consulta (atualização automática)
  const body = { ...base, rows: rp.rows, col: rp.col, metrics: rp.metrics, sort: rp.sort, limit: rp.limit, texto: rp.texto, having: rp.having }
  const key = JSON.stringify({ body, dataVersion })
  const [data, setData] = useState<ReportResp | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const gen = useRef(0)
  useEffect(() => {
    const g = ++gen.current
    setLoading(true); setError(null)
    const t = setTimeout(() => {
      api.post<ReportResp>('/api/report', body)
        .then((r) => { if (g === gen.current) setData(r) })
        .catch((e) => { if (g === gen.current) setError(e.message) })
        .finally(() => { if (g === gen.current) setLoading(false) })
    }, 150)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  useEffect(() => { setSelected(null) }, [key])

  // ---------------------------------------------------------------- colunas da grade
  const [clientSort, setClientSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null)
  useEffect(() => setClientSort(null), [key])
  const grid = useMemo(() => {
    if (!data) return { columns: [] as GridCol[], rows: [] as GridRow[] }
    const ix = (c: string) => data.columns.indexOf(c)
    const cols: GridCol[] = []
    rp.rows.forEach((d, i) => {
      const hasDesc = data.columns.includes(`${d}__desc`)
      cols.push({
        key: d, label: dimLabel(d), type: 'text', sticky: i === 0,
        width: d === 'filial' ? 230 : d === 'fornecedor' ? 250 : d === 'descr_item' || d === 'item' ? 240 : hasDesc ? 230 : 110,
        render: (r) => r.cells.__sub
          ? (r.cells.__level === i
            ? <span className="flex min-w-0 items-center gap-1.5"><Sigma className="h-3.5 w-3.5 shrink-0 text-accent" /><DimCell dim={d} code={r.cells[d]} desc={r.cells[`${d}__desc`]} /></span>
            : null)
          : (r.cells[d] == null ? <span className="italic text-muted">(vazio)</span> : <DimCell dim={d} code={r.cells[d]} desc={r.cells[`${d}__desc`]} />),
      })
    })
    if (data.columnsMeta.length) {
      for (const cm of data.columnsMeta) {
        cols.push({ key: cm.key, label: `${cm.group === 'TOTAL' ? 'Total' : rp.col === 'competencia' ? fmtComp(cm.group) : cm.group} · ${metricLabel(cm.metric)}`,
          type: data.types[ix(cm.key)] ?? 'money', className: cm.group === 'TOTAL' ? 'font-semibold' : '' })
      }
    } else {
      for (const m of data.metrics) cols.push({ key: m, label: metricLabel(m), type: data.types[ix(m)] ?? 'money', width: m.startsWith('cst') ? 100 : m === 'unid' ? 90 : undefined })
    }
    let rows: GridRow[] = data.rows.map((r, i) => ({ id: `r${i}`, cells: Object.fromEntries(data.columns.map((c, j) => [c, r[j]])) }))
    if (clientSort) {
      const m = clientSort.dir === 'asc' ? 1 : -1
      rows = [...rows].sort((a, b) => ((a.cells[clientSort.key] ?? -Infinity) > (b.cells[clientSort.key] ?? -Infinity) ? 1 : -1) * m)
    }
    if (rp.subtotais && rp.rows.length > 1 && !data.truncated && !clientSort) rows = withSubtotals(rows, rp.rows, cols, rp.sort)
    return { columns: cols, rows }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, rp.subtotais, clientSort])

  const onSort = (k: string) => {
    if (k in metricDefs || rp.rows.includes(k)) {
      upd({ sort: { by: k, dir: rp.sort.by === k && rp.sort.dir === 'desc' ? 'asc' : 'desc' } })
    } else {
      setClientSort((s) => (s?.key === k ? { key: k, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key: k, dir: 'desc' }))
    }
  }
  const gridSort = clientSort ?? (rp.sort ? { key: rp.sort.by, dir: rp.sort.dir } : null)

  // ---------------------------------------------------------------- notas da linha clicada
  const [selected, setSelected] = useState<{ id: string; path: PathItem[] } | null>(null)
  const onSelect = (r: GridRow) => {
    const lvl = r.cells.__sub ? r.cells.__level + 1 : rp.rows.length
    const path: PathItem[] = rp.rows.slice(0, lvl).map((d) => [d, r.cells[d], r.cells[`${d}__desc`] ? `${codeLabel(d, r.cells[d])} ${r.cells[`${d}__desc`]}` : codeLabel(d, r.cells[d])])
    if (!path.length) return
    setSelected({ id: r.id, path })
  }
  const runExport = async (url: string, b: any, label: string) => {
    const id = toast.loading(`Gerando ${label}…`)
    try {
      const r = await api.post(url, b)
      toast.success(`${label} pronto${r.linhas != null ? ` — ${fmtInt(r.linhas)} linhas` : ''}`, { id, description: r.path, duration: 9000,
        action: { label: 'Abrir pasta', onClick: () => api.post('/api/open-folder', { path: r.path }) } })
      download(r.url)
    } catch (e: any) { toast.error(e.message, { id }) }
  }

  // ---------------------------------------------------------------- arrastar e soltar
  const dragRef = useRef<Drag | null>(null)
  const dropTo = (zone: 'rows' | 'col' | 'metrics', index?: number) => {
    const d = dragRef.current
    dragRef.current = null
    if (!d) return
    if (zone === 'metrics') {
      if (d.kind !== 'metric') { toast.message('Arraste um valor (ex.: ICMS) para esta área'); return }
      const list = rp.metrics.filter((m) => m !== d.key)
      list.splice(index ?? list.length, 0, d.key)
      upd({ metrics: list })
      return
    }
    if (d.kind !== 'dim') { toast.message('Arraste uma dimensão (ex.: Fornecedor) para esta área'); return }
    if (zone === 'col') {
      upd({ col: d.key, rows: rp.rows.filter((x) => x !== d.key) })
      return
    }
    const list = rp.rows.filter((x) => x !== d.key)
    list.splice(index ?? list.length, 0, d.key)
    upd({ rows: list, col: rp.col === d.key ? null : rp.col })
  }
  const addRow = (k: string) => upd({ rows: [...rp.rows.filter((x) => x !== k), k], col: rp.col === k ? null : rp.col })
  const toggleMetric = (k: string) => upd({ metrics: rp.metrics.includes(k) ? rp.metrics.filter((m) => m !== k) : [...rp.metrics, k] })

  const sortOptions = [
    ...rp.metrics.filter((m) => metricDefs[m]?.type !== 'text').map((m) => ({ k: m, l: metricLabel(m) })),
    ...rp.rows.map((d) => ({ k: d, l: dimLabel(d) })),
  ]
  const sortIsDim = rp.rows.includes(rp.sort.by)
  const [cfgCollapsed, setCfgCollapsed] = useCollapsed('report-config')
  const mx = useMaximize()
  const docsH = useDragHeight('report-docs', 280)

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-3 tall:gap-3 tall:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <FilterBar />
      </div>
      <RulesChip />
      <div className="flex min-h-0 flex-1 gap-3">
        <SidePanel id="report-fields" title="Campos" defaultWidth={264} min={200} max={480}>
          <FieldList rp={rp} onDrag={(d) => { dragRef.current = d }} addRow={addRow} setCol={(k) => upd({ col: k, rows: rp.rows.filter((x) => x !== k) })} toggleMetric={toggleMetric} />
        </SidePanel>

        <div className="flex min-w-0 flex-1 flex-col gap-2 tall:gap-3">
          {/* áreas de montagem */}
          {cfgCollapsed ? (
            <Card className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 text-[12.5px]">
              <span className="text-muted">Linhas:</span><b className="font-medium">{rp.rows.map(dimLabel).join(' › ') || '—'}</b>
              {rp.col && <><span className="text-muted">Colunas:</span><b className="font-medium">{dimLabel(rp.col)}</b></>}
              <span className="text-muted">Valores:</span><b className="truncate font-medium">{rp.metrics.map(metricLabel).join(', ')}</b>
              <div className="flex-1" />
              <CollapseToggle collapsed onToggle={() => setCfgCollapsed(false)} label="montagem" />
            </Card>
          ) : (
          <Card className="p-2.5">
            <div className="grid grid-cols-1 gap-2 lg:grid-cols-[1.4fr_0.8fr_1.4fr]">
              <Zone title="Linhas" icon={<Rows3 className="h-4 w-4" />} hint="Arraste dimensões (Unidade, Fornecedor, CFOP…)" onDrop={() => dropTo('rows')}>
                {rp.rows.map((d, i) => (
                  <Chip key={d} label={dimLabel(d)} n={i + 1} onRemove={() => upd({ rows: rp.rows.filter((x) => x !== d) })}
                    onDragStart={() => { dragRef.current = { kind: 'dim', key: d, from: 'rows', index: i } }} onDrop={() => dropTo('rows', i)} />
                ))}
              </Zone>
              <Zone title="Colunas" icon={<Columns3 className="h-4 w-4" />} hint="Opcional: Competência, UF, CST…" onDrop={() => dropTo('col')}>
                {rp.col && <Chip label={dimLabel(rp.col)} tone="info" onRemove={() => upd({ col: null })}
                  onDragStart={() => { dragRef.current = { kind: 'dim', key: rp.col!, from: 'col' } }} onDrop={() => dropTo('col')} />}
              </Zone>
              <Zone title="Valores" icon={<Sigma className="h-4 w-4" />} hint="Arraste valores (Valor contábil, ICMS, PIS…)" onDrop={() => dropTo('metrics')}>
                {rp.metrics.map((m, i) => (
                  <Chip key={m} label={metricLabel(m)} tone="ok" onRemove={() => upd({ metrics: rp.metrics.filter((x) => x !== m) })}
                    onDragStart={() => { dragRef.current = { kind: 'metric', key: m, from: 'metrics', index: i } }} onDrop={() => dropTo('metrics', i)} />
                ))}
              </Zone>
            </div>
          </Card>
          )}

          {/* ordenação, filtros, opções */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-lg border bg-panel pl-2.5">
              <span className="text-[12.5px] text-muted">Ordenar por</span>
              <Select className="border-0" value={rp.sort.by} onChange={(e) => upd({ sort: { ...rp.sort, by: e.target.value } })}>
                {sortOptions.map((o) => <option key={o.k} value={o.k}>{o.l}</option>)}
              </Select>
            </div>
            <div className="inline-flex h-[34px] items-center rounded-lg bg-sunken p-0.5">
              {(['desc', 'asc'] as const).map((d) => (
                <button key={d} onClick={() => upd({ sort: { ...rp.sort, dir: d } })}
                  className={cx('inline-flex h-full items-center gap-1.5 rounded-md px-2.5 text-[12.5px] font-medium', rp.sort.dir === d ? 'bg-panel shadow-sm' : 'text-muted hover:text-fg')}>
                  {d === 'desc' ? <ArrowDownWideNarrow className="h-4 w-4" /> : <ArrowUpNarrowWide className="h-4 w-4" />}
                  {sortIsDim ? (d === 'desc' ? 'Z → A' : 'A → Z') : (d === 'desc' ? 'Maior → menor' : 'Menor → maior')}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5 rounded-lg border bg-panel pl-2.5">
              <span className="text-[12.5px] text-muted">Mostrar</span>
              <Select className="border-0" value={rp.limit} onChange={(e) => upd({ limit: Number(e.target.value) })}>
                {LIMITS.map((n) => <option key={n} value={n}>{n === 20000 ? 'até 20.000 linhas' : `${fmtInt(n)} primeiras`}</option>)}
              </Select>
            </div>
            <Input className="w-[240px]" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Filtrar texto nas linhas…" icon={<Search className="h-4 w-4" />} />
            <HavingEditor value={rp.having} metrics={meta.metrics.filter((m) => m.type !== 'text' && !m.rowLevel).map((m) => [m.key, m.label] as [string, string])} onChange={(h) => upd({ having: h })} />
            <Tip content={data?.truncated ? 'Disponível quando todas as linhas couberem na tela (aumente "Mostrar" ou filtre)' : rp.rows.length < 2 ? 'Use ao menos 2 dimensões nas linhas' : 'Mostra o total de cada grupo antes dos seus itens'}>
              <div className={cx('rounded-lg border bg-panel px-2.5 py-1.5', (data?.truncated || rp.rows.length < 2) && 'opacity-50')}>
                <Switch checked={rp.subtotais} onChange={(v) => upd({ subtotais: v })} label="Subtotais" />
              </div>
            </Tip>
            <div className="flex-1" />
            {!cfgCollapsed && <CollapseToggle collapsed={false} onToggle={() => setCfgCollapsed(true)} label="montagem" />}
            <Layouts rp={rp} upd={upd} />
            <Button variant="primary" icon={<ArrowDownToLine className="h-4 w-4" />} disabled={!data || !rp.metrics.length}
              onClick={() => runExport('/api/export/report', { ...body, appliedFilterName: state.appliedFilterName }, 'Excel do relatório')}>Excel</Button>
          </div>

          {/* chips de filtros por valor */}
          {rp.having.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {rp.having.map((h, i) => (
                <Badge key={i} tone="accent" className="py-1">
                  Somente linhas com {metricLabel(h.metric)} {HAVING_OPS[h.op]} {!['zero', 'nao_zero'].includes(h.op) && <b>{h.value}</b>}
                  <button className="ml-1 opacity-70 hover:opacity-100" onClick={() => upd({ having: rp.having.filter((_, j) => j !== i) })}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
          )}

          {/* resultado */}
          <div className="flex items-center gap-3 text-[12px] text-muted">
            {error ? <span className="text-bad">{error}</span> : data ? (
              <>
                <span><b className="text-fg">{fmtInt(data.rowCount ?? 1)}</b> linha(s){data.truncated ? <span className="text-warn"> · exibindo as {fmtInt(data.rows.length)} primeiras pela ordenação; a linha Total considera todas</span> : ''}</span>
                <Tip content="O relatório lê a base consolidada: o valor e o ICMS/IPI vêm do SPED Fiscal; o PIS/COFINS da EFD-Contribuições já está atribuído a uma única linha. Créditos sem par no SPED Fiscal entram como 'Somente EFD' com valor contábil zero. Assim nenhum valor é contado duas vezes, e o Total é calculado direto da base.">
                  <span className="inline-flex items-center gap-1 text-ok"><ShieldCheck className="h-3.5 w-3.5" />Consolidado SPED Fiscal + EFD-Contribuições, sem duplicidade</span>
                </Tip>
                <span className="inline-flex items-center gap-1"><Database className="h-3.5 w-3.5" />{data.source.replace('fato_entradas_consolidadas', 'itens (fato)')} · {data.ms} ms</span>
              </>
            ) : null}
            <div className="flex-1" />
            <MaxButton on={mx.on} onClick={mx.toggle} size="icon-sm" />
          </div>
          <div className="flex min-h-0 flex-1 flex-col">
            {mx.on && <div className="fixed inset-0 z-30 bg-black/30" onClick={mx.toggle} />}
            <div className={cx('min-h-[200px] flex-1', mx.on && 'fixed inset-2 z-40 flex flex-col rounded-xl border bg-bg p-2 shadow-pop')}>
              {mx.on && <div className="flex items-center gap-2 px-1 pb-2 text-[13px] font-semibold">Relatório dinâmico<span className="font-normal text-muted">· {fmtInt(data?.rowCount ?? 0)} linha(s)</span><div className="flex-1" /><MaxButton on onClick={mx.toggle} size="icon-sm" /></div>}
              <div className={cx(mx.on ? 'min-h-0 flex-1' : 'h-full')}>
              {!rp.metrics.length ? (
                <Card className="flex h-full items-center justify-center text-[13px] text-muted">Escolha ao menos um valor na área “Valores”.</Card>
              ) : (
                <DataGrid columns={grid.columns} rows={grid.rows} totals={data?.totals} loading={loading} selectedId={selected?.id}
                  onSelect={onSelect} sort={gridSort} onSort={onSort} rowHeight={32} dense
                  emptyText={error ? 'Não foi possível montar o relatório' : 'Nenhum dado para os filtros atuais'} />
              )}
              </div>
            </div>
            {selected && docsH.handle}
            {selected && (
              <div className="flex shrink-0 flex-col" style={{ height: docsH.h }}>
                <DocsPanel path={selected.path} base={base} ctx={{ ...base, hierarchy: rp.rows }} onClose={() => setSelected(null)} onExport={runExport} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------
function withSubtotals(rows: GridRow[], dims: string[], cols: GridCol[], sort: { by: string; dir: string }): GridRow[] {
  const numCols = cols.filter((c) => ADDITIVE_T.has(c.type) && !c.key.endsWith('n_docs')).map((c) => c.key)
  const sortKey = numCols.includes(sort.by) ? sort.by : numCols.find((k) => k.endsWith(`${SEP}${sort.by}`)) ?? numCols[0]
  const m = sort.dir === 'asc' ? 1 : -1
  const out: GridRow[] = []
  const walk = (subset: GridRow[], level: number, prefix: string) => {
    if (level >= dims.length - 1) { out.push(...subset); return }
    const groups = new Map<string, GridRow[]>()
    for (const r of subset) {
      const k = JSON.stringify(r.cells[dims[level]] ?? null)
      if (!groups.has(k)) groups.set(k, [])
      groups.get(k)!.push(r)
    }
    const sums = [...groups.entries()].map(([k, list]) => {
      const cells: Record<string, any> = { __sub: true, __level: level }
      for (let i = 0; i <= level; i++) { cells[dims[i]] = list[0].cells[dims[i]]; cells[`${dims[i]}__desc`] = list[0].cells[`${dims[i]}__desc`] }
      for (const c of numCols) cells[c] = list.reduce((a, r) => a + (Number(r.cells[c]) || 0), 0)
      if ('preco_medio' in list[0].cells && cells.qtd) cells.preco_medio = (cells.vl_item ?? 0) / cells.qtd
      return { k, list, cells }
    })
    if (sortKey && !dims.includes(sort.by)) sums.sort((a, b) => ((a.cells[sortKey] ?? 0) - (b.cells[sortKey] ?? 0)) * m)
    for (const g of sums) {
      out.push({ id: `${prefix}|s${level}|${g.k}`, cells: g.cells })
      walk(g.list, level + 1, `${prefix}|${g.k}`)
    }
  }
  walk(rows, 0, '')
  return out.map((r) => (r.cells.__sub ? { ...r, cells: { ...r.cells } } : r))
}

function Zone({ title, icon, hint, children, onDrop }: { title: string; icon: ReactNode; hint: string; children: ReactNode; onDrop: () => void }) {
  const [over, setOver] = useState(false)
  const empty = !children || (Array.isArray(children) && children.length === 0)
  return (
    <div onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); onDrop() }}
      className={cx('min-h-[58px] rounded-xl border-2 border-dashed px-2 py-1.5 transition-colors', over ? 'border-accent bg-accent/5' : 'border-line bg-sunken/40')}>
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{icon}{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {empty ? <span className="px-1 py-1 text-[12px] text-muted/80">{hint}</span> : children}
      </div>
    </div>
  )
}

function Chip({ label, n, tone = 'accent', onRemove, onDragStart, onDrop }: { label: string; n?: number; tone?: 'accent' | 'info' | 'ok'; onRemove: () => void; onDragStart: () => void; onDrop: () => void }) {
  const toneCls = { accent: 'border-accent/30 bg-accent/10', info: 'border-info/30 bg-info/10', ok: 'border-ok/30 bg-ok/10' }[tone]
  return (
    <div draggable onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; onDragStart() }}
      onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); e.stopPropagation(); onDrop() }}
      className={cx('group inline-flex h-[26px] cursor-grab items-center gap-1 rounded-lg border pl-1 pr-1 text-[12px] font-medium active:cursor-grabbing', toneCls)}>
      <GripVertical className="h-3.5 w-3.5 text-muted" />
      {n != null && <span className="text-[11px] text-muted">{n}.</span>}
      <span>{label}</span>
      <button onClick={onRemove} className="ml-0.5 rounded p-0.5 text-muted hover:bg-black/5 hover:text-bad"><X className="h-3.5 w-3.5" /></button>
    </div>
  )
}

function FieldList({ rp, onDrag, addRow, setCol, toggleMetric }: { rp: ReportState; onDrag: (d: Drag) => void; addRow: (k: string) => void; setCol: (k: string) => void; toggleMetric: (k: string) => void }) {
  const { meta } = useApp()
  const [q, setQ] = useState('')
  const n = q.trim().toLowerCase()
  const dims = meta.dimensions.filter((d) => !n || d.label.toLowerCase().includes(n))
  const mets = meta.metrics.filter((m) => !n || m.label.toLowerCase().includes(n))
  return (
    <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b p-2.5"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar campo…" icon={<Search className="h-4 w-4" />} /></div>
      <div className="min-h-0 flex-1 overflow-auto p-1.5">
        <div className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Dimensões</div>
        {dims.map((d) => {
          const inRows = rp.rows.includes(d.key), inCol = rp.col === d.key
          return (
            <div key={d.key} draggable onDragStart={() => onDrag({ kind: 'dim', key: d.key })}
              className={cx('group flex cursor-grab items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12.5px] hover:bg-sunken', (inRows || inCol) && 'text-accent')}>
              <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted/60" />
              <span className="min-w-0 flex-1 truncate">{d.label}</span>
              {inRows && <Badge tone="accent">linha</Badge>}{inCol && <Badge tone="info">coluna</Badge>}
              {!inRows && <Tip content="Adicionar às linhas"><button onClick={() => addRow(d.key)} className="rounded p-0.5 text-muted opacity-0 hover:bg-line/70 hover:text-fg group-hover:opacity-100"><Plus className="h-3.5 w-3.5" /></button></Tip>}
              {!inCol && <Tip content="Usar como colunas"><button onClick={() => setCol(d.key)} className="rounded p-0.5 text-muted opacity-0 hover:bg-line/70 hover:text-fg group-hover:opacity-100"><Columns3 className="h-3.5 w-3.5" /></button></Tip>}
            </div>
          )
        })}
        <div className="mt-2 px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Valores</div>
        {mets.map((m) => {
          const on = rp.metrics.includes(m.key)
          return (
            <div key={m.key} draggable onDragStart={() => onDrag({ kind: 'metric', key: m.key })} onClick={() => toggleMetric(m.key)}
              className={cx('flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] hover:bg-sunken', on && 'text-ok')}>
              <span className={cx('flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px]', on ? 'border-ok bg-ok text-white' : 'bg-panel')}>{on ? '✓' : ''}</span>
              <span className="min-w-0 flex-1 truncate">{m.label}</span>
              {m.rowLevel && <span className="text-[10.5px] text-warn">lento</span>}
            </div>
          )
        })}
      </div>
    </Card>
  )
}

function HavingEditor({ value, metrics, onChange }: { value: Having[]; metrics: [string, string][]; onChange: (h: Having[]) => void }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<Having[]>(value)
  useEffect(() => { if (open) setDraft(value.length ? value : [{ metric: 'vl_contabil', op: '>', value: '' }]) }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  const set = (i: number, p: Partial<Having>) => setDraft((d) => d.map((h, j) => (j === i ? { ...h, ...p } : h)))
  return (
    <Popover open={open} onOpenChange={setOpen} align="start" trigger={
      <Button icon={<Filter className="h-4 w-4" />}>Filtros por valor {value.length ? <Badge tone="accent">{value.length}</Badge> : null}</Button>
    }>
      <div className="w-[520px] space-y-2 p-3">
        <div className="text-[12px] text-muted">Mostra só as linhas do relatório cujo total atende às condições (ex.: PIS igual a zero, valor contábil maior que 10.000). Os totais passam a considerar só essas linhas.</div>
        {draft.map((h, i) => (
          <div key={i} className="flex items-center gap-2">
            <Select className="w-[190px]" value={h.metric} onChange={(e) => set(i, { metric: e.target.value })}>
              {metrics.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
            <Select className="w-[160px]" value={h.op} onChange={(e) => set(i, { op: e.target.value })}>
              {Object.entries(HAVING_OPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
            {!['zero', 'nao_zero'].includes(h.op) && <Input className="flex-1" value={h.value} onChange={(e) => set(i, { value: e.target.value })} placeholder="ex.: 10.000,00" />}
            <Button size="icon-sm" variant="ghost" onClick={() => setDraft((d) => d.filter((_, j) => j !== i))}><X className="h-4 w-4" /></Button>
          </div>
        ))}
        <div className="flex items-center justify-between pt-1">
          <Button size="sm" variant="ghost" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setDraft((d) => [...d, { metric: 'vl_contabil', op: '>', value: '' }])}>Condição</Button>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => { onChange([]); setOpen(false) }}>Remover todas</Button>
            <Button size="sm" variant="primary" onClick={() => { onChange(draft.filter((h) => ['zero', 'nao_zero'].includes(h.op) || String(h.value).trim() !== '')); setOpen(false) }}>Aplicar</Button>
          </div>
        </div>
      </div>
    </Popover>
  )
}

function Layouts({ rp, upd }: { rp: ReportState; upd: (p: Partial<ReportState>) => void }) {
  const [saveOpen, setSaveOpen] = useState(false)
  const [nome, setNome] = useState('')
  const apply = (l: ReportLayout) => upd({ rows: l.rows, col: l.col, metrics: l.metrics, sort: { by: l.metrics.find((m) => !m.startsWith('cst') && m !== 'unid') ?? 'vl_contabil', dir: 'desc' }, having: [], texto: '' })
  return (
    <>
      <Menu trigger={<Button icon={<LayoutTemplate className="h-4 w-4" />}>Modelos</Button>}>
        <MenuLabel>Modelos prontos</MenuLabel>
        {PRESETS.map((l) => <MenuItem key={l.nome} onSelect={() => apply(l)}>{l.nome}</MenuItem>)}
        {rp.layouts.length > 0 && <><MenuSep /><MenuLabel>Meus modelos</MenuLabel></>}
        {rp.layouts.map((l, i) => (
          <MenuItem key={i} onSelect={() => apply(l)}>
            <span className="flex items-center justify-between gap-3"><span>{l.nome}</span>
              <span role="button" className="text-muted hover:text-bad" onClick={(e) => { e.stopPropagation(); e.preventDefault(); upd({ layouts: rp.layouts.filter((_, j) => j !== i) }) }}><Trash2 className="h-3.5 w-3.5" /></span>
            </span>
          </MenuItem>
        ))}
        <MenuSep />
        <MenuItem icon={<BookmarkPlus className="h-4 w-4" />} onSelect={() => setTimeout(() => setSaveOpen(true), 50)}>Salvar montagem atual…</MenuItem>
      </Menu>
      <Dialog open={saveOpen} onOpenChange={setSaveOpen} title="Salvar modelo de relatório" description="Guarda linhas, colunas e valores para reabrir com um clique."
        footer={<><Button variant="ghost" onClick={() => setSaveOpen(false)}>Cancelar</Button>
          <Button variant="primary" disabled={!nome.trim()} onClick={() => { upd({ layouts: [...rp.layouts, { nome: nome.trim(), rows: rp.rows, col: rp.col, metrics: rp.metrics }] }); setSaveOpen(false); setNome(''); toast.success('Modelo salvo') }}>Salvar</Button></>}>
        <Field label="Nome do modelo"><Input autoFocus value={nome} onChange={(e) => setNome(e.target.value)} placeholder="ex.: Compras por fornecedor e item" /></Field>
      </Dialog>
    </>
  )
}

