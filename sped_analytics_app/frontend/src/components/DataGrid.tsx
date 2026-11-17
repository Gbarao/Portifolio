import { useVirtualizer } from '@tanstack/react-virtual'
import { ArrowDown, ArrowUp, ChevronRight, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { COLUMN_LABELS, fmtCell, fmtCnpj, isNumeric } from '../lib/format'
import type { ColType, Table } from '../lib/types'
import { cx } from './ui'

export interface GridCol {
  key: string
  label: string
  type: ColType
  width?: number
  sticky?: boolean
  render?: (row: GridRow) => ReactNode
  className?: string
}

export interface GridRow {
  id: string
  depth?: number
  cells: Record<string, any>
  kind?: 'row' | 'loading' | 'note'
  expandable?: boolean
  expanded?: boolean
  note?: string
}

interface Props {
  columns: GridCol[]
  rows: GridRow[]
  totals?: Record<string, any> | null
  totalsLabel?: string
  loading?: boolean
  emptyText?: ReactNode
  selectedId?: string | null
  onSelect?: (row: GridRow) => void
  onToggle?: (row: GridRow) => void
  onActivate?: (row: GridRow) => void
  sort?: { key: string; dir: 'asc' | 'desc' } | null
  onSort?: (key: string) => void
  rowHeight?: number
  treeKey?: string
  checkable?: boolean
  checked?: Set<string>
  onCheck?: (ids: Set<string>) => void
  dense?: boolean
  onEndReached?: () => void
}

const DEFAULT_W: Record<string, number> = { money: 120, qty: 100, price: 110, int: 84, pct: 84, date: 104, bool: 70, text: 150 }

export function DataGrid({
  columns, rows, totals, totalsLabel = 'Total', loading, emptyText, selectedId, onSelect, onToggle, onActivate,
  sort, onSort, rowHeight = 34, treeKey, checkable, checked, onCheck, dense, onEndReached,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [widths, setWidths] = useState<Record<string, number>>({})
  // largura automática das colunas numéricas pelo maior valor formatado (totais + amostra das linhas)
  const autoW = useMemo(() => {
    const out: Record<string, number> = {}
    const sample = rows.length > 400 ? rows.slice(0, 400) : rows
    for (const c of columns) {
      if (c.width || !isNumeric(c.type)) continue
      let len = c.label.length * 0.8
      const consider = (v: any) => { if (v != null && v !== '') len = Math.max(len, fmtCell(v, c.type).length) }
      if (totals) consider(totals[c.key])
      for (const r of sample) consider(r.cells[c.key])
      out[c.key] = Math.max(DEFAULT_W[c.type] ?? 110, Math.min(240, Math.round(len * 7.6 + 30)))
    }
    return out
  }, [columns, rows, totals])
  const colW = useCallback((c: GridCol) => widths[c.key] ?? c.width ?? autoW[c.key] ?? DEFAULT_W[c.type] ?? 140, [widths, autoW])
  const checkW = checkable ? 40 : 0
  const total = useMemo(() => columns.reduce((a, c) => a + colW(c), 0) + checkW, [columns, colW, checkW])
  const stickyOffsets = useMemo(() => {
    const out: Record<string, number> = {}
    let acc = checkW
    for (const c of columns) { if (c.sticky) { out[c.key] = acc; acc += colW(c) } }
    return out
  }, [columns, colW, checkW])

  const virt = useVirtualizer({ count: rows.length, getScrollElement: () => scrollRef.current, estimateSize: () => rowHeight, overscan: 16 })
  const vItems = virt.getVirtualItems()
  const lastIdx = vItems.length ? vItems[vItems.length - 1].index : 0
  useEffect(() => { if (onEndReached && rows.length > 0 && lastIdx >= rows.length - 40) onEndReached() }, [lastIdx, rows.length, onEndReached])

  // redimensionamento de colunas
  const drag = useRef<{ key: string; x: number; w: number } | null>(null)
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!drag.current) return
      const { key, x, w } = drag.current
      setWidths((s) => ({ ...s, [key]: Math.max(60, w + e.clientX - x) }))
    }
    const up = () => { drag.current = null; document.body.style.cursor = '' }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [])

  const allIds = useMemo(() => rows.filter((r) => (r.kind ?? 'row') === 'row').map((r) => r.id), [rows])
  const allChecked = checkable && allIds.length > 0 && allIds.every((id) => checked?.has(id))

  const cellStyle = (c: GridCol): React.CSSProperties => ({
    width: colW(c), minWidth: colW(c), maxWidth: colW(c),
    ...(c.sticky ? { position: 'sticky', left: stickyOffsets[c.key], zIndex: 2 } : {}),
  })

  const renderValue = (c: GridCol, r: GridRow) => {
    if (c.render) return c.render(r)
    const v = r.cells[c.key]
    if (c.type === 'text' && typeof v === 'string' && /^\d{14}$/.test(v)) return fmtCnpj(v)
    return fmtCell(v, c.type, c.key)
  }

  return (
    <div ref={scrollRef} className="relative h-full w-full overflow-auto rounded-xl border bg-panel">
      <div style={{ width: total, minWidth: '100%' }} className="relative">
        {/* cabeçalho */}
        <div className="sticky top-0 z-20 flex border-b bg-sunken/95 backdrop-blur" style={{ height: 36 }}>
          {checkable && (
            <div className="sticky left-0 z-[3] flex items-center justify-center bg-sunken" style={{ width: checkW, minWidth: checkW }}>
              <input type="checkbox" className="h-3.5 w-3.5 accent-[rgb(var(--accent))]" checked={!!allChecked}
                onChange={() => onCheck?.(allChecked ? new Set() : new Set(allIds))} />
            </div>
          )}
          {columns.map((c) => {
            const num = isNumeric(c.type)
            const active = sort?.key === c.key
            return (
              <div key={c.key} style={cellStyle(c)}
                className={cx('group relative flex items-center bg-sunken px-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted',
                  num && 'justify-end text-right', onSort && 'cursor-pointer hover:text-fg', c.sticky && 'shadow-[1px_0_0_rgb(var(--line))]')}
                onClick={() => onSort?.(c.key)} title={c.label}>
                <span className="truncate">{c.label}</span>
                {active && (sort!.dir === 'desc' ? <ArrowDown className="ml-1 h-3 w-3 shrink-0" /> : <ArrowUp className="ml-1 h-3 w-3 shrink-0" />)}
                <span onMouseDown={(e) => { e.stopPropagation(); drag.current = { key: c.key, x: e.clientX, w: colW(c) }; document.body.style.cursor = 'col-resize' }}
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-1.5 bottom-1.5 w-1.5 cursor-col-resize rounded opacity-0 hover:bg-accent/40 group-hover:opacity-100" />
              </div>
            )
          })}
        </div>

        {/* corpo virtualizado */}
        <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
          {virt.getVirtualItems().map((vi) => {
            const r = rows[vi.index]
            const kind = r.kind ?? 'row'
            const selected = selectedId != null && r.id === selectedId
            const isChecked = checked?.has(r.id)
            if (kind !== 'row') {
              return (
                <div key={r.id} className="absolute left-0 flex w-full items-center border-b border-line/60 text-[12px] text-muted"
                  style={{ top: 0, transform: `translateY(${vi.start}px)`, height: rowHeight }}>
                  <div className="sticky left-0 flex items-center gap-2 px-3" style={{ paddingLeft: 12 + (r.depth ?? 0) * 20 + 22 }}>
                    {kind === 'loading' ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Carregando…</> : r.note}
                  </div>
                </div>
              )
            }
            const depth = r.depth ?? 0
            return (
              <div key={r.id}
                className={cx('group/row absolute left-0 flex w-full cursor-default border-b border-line/60 text-[13px] transition-colors',
                  selected ? 'bg-accent/[0.08]' : r.cells.__sub ? 'bg-sunken/80 font-semibold hover:bg-sunken' : depth > 0 ? 'bg-sunken/30 hover:bg-sunken' : 'hover:bg-sunken/70')}
                style={{ top: 0, transform: `translateY(${vi.start}px)`, height: rowHeight }}
                onClick={() => onSelect?.(r)} onDoubleClick={() => (r.expandable ? onToggle?.(r) : onActivate?.(r))}>
                {checkable && (
                  <div className={cx('sticky left-0 z-[2] flex items-center justify-center', selected ? 'bg-[rgb(var(--panel))]' : 'bg-panel')}
                    style={{ width: checkW, minWidth: checkW }}>
                    <input type="checkbox" className="h-3.5 w-3.5 accent-[rgb(var(--accent))]" checked={!!isChecked}
                      onClick={(e) => e.stopPropagation()}
                      onChange={() => { const n = new Set(checked); isChecked ? n.delete(r.id) : n.add(r.id); onCheck?.(n) }} />
                  </div>
                )}
                {columns.map((c) => {
                  const num = isNumeric(c.type)
                  const isTree = treeKey === c.key
                  return (
                    <div key={c.key} style={cellStyle(c)}
                      className={cx('flex items-center overflow-hidden px-3',
                        num && 'num justify-end text-right', dense && 'text-[12.5px]', c.className,
                        c.sticky && 'shadow-[1px_0_0_rgb(var(--line))]',
                        c.sticky && (selected ? 'bg-[color-mix(in_srgb,rgb(var(--accent))_8%,rgb(var(--panel)))]' : depth > 0 ? 'bg-[color-mix(in_srgb,rgb(var(--sunken))_30%,rgb(var(--panel)))] group-hover/row:bg-sunken' : 'bg-panel group-hover/row:bg-[color-mix(in_srgb,rgb(var(--sunken))_70%,rgb(var(--panel)))]'))}>
                      {isTree ? (
                        <div className="flex min-w-0 items-center gap-1" style={{ paddingLeft: depth * 20 }}>
                          {r.expandable ? (
                            <button onClick={(e) => { e.stopPropagation(); onToggle?.(r) }}
                              className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted hover:bg-line/70 hover:text-fg focus-ring">
                              <ChevronRight className={cx('h-4 w-4 transition-transform', r.expanded && 'rotate-90')} />
                            </button>
                          ) : <span className="w-5 shrink-0" />}
                          <div className="min-w-0 flex-1 truncate">{renderValue(c, r)}</div>
                        </div>
                      ) : <span className="min-w-0 truncate">{renderValue(c, r)}</span>}
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>

        {/* totais */}
        {totals && rows.length > 0 && (
          <div className="sticky bottom-0 z-20 flex border-t-2 border-line bg-sunken/95 text-[13px] font-semibold backdrop-blur" style={{ height: 36 }}>
            {checkable && <div className="sticky left-0 z-[3] bg-sunken" style={{ width: checkW, minWidth: checkW }} />}
            {columns.map((c, i) => (
              <div key={c.key} style={cellStyle(c)}
                className={cx('flex items-center overflow-hidden bg-sunken px-3', isNumeric(c.type) && 'num justify-end',
                  c.sticky && 'shadow-[1px_0_0_rgb(var(--line))]')}>
                <span className="truncate">{i === 0 ? totalsLabel : isNumeric(c.type) ? fmtCell(totals[c.key], c.type) : ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {!loading && rows.length === 0 && (
        <div className="absolute inset-0 top-9 flex items-center justify-center text-[13px] text-muted">{emptyText ?? 'Sem dados para os filtros atuais'}</div>
      )}
      {loading && (
        <div className="pointer-events-none absolute inset-x-0 top-9 h-0.5 overflow-hidden">
          <div className="loading-bar h-full w-1/4 bg-accent" />
        </div>
      )}
    </div>
  )
}

/** Converte a resposta tabular da API em colunas/linhas da grade (tabelas simples). */
export function tableToGrid(t: Table | null, opts: { hide?: string[]; labels?: Record<string, string>; widths?: Record<string, number>; sticky?: number; idCol?: string } = {}) {
  if (!t) return { columns: [] as GridCol[], rows: [] as GridRow[] }
  const hide = new Set(opts.hide || [])
  const columns: GridCol[] = t.columns.map((c, i) => ({
    key: c, label: opts.labels?.[c] ?? COLUMN_LABELS[c] ?? c, type: t.types[i] ?? 'text',
    width: opts.widths?.[c] ?? (c === 'chave' ? 340 : c === 'mensagem' || c === 'caminho_origem' ? 360 : c.includes('razao') || c.includes('nome') || c.includes('descr') ? 220 : undefined),
  })).filter((c) => !hide.has(c.key)).map((c, i) => ({ ...c, sticky: i < (opts.sticky ?? 0) }))
  const idIdx = opts.idCol ? t.columns.indexOf(opts.idCol) : -1
  const rows: GridRow[] = t.rows.map((r, i) => ({
    id: idIdx >= 0 ? String(r[idIdx]) : String(i),
    cells: Object.fromEntries(t.columns.map((c, j) => [c, r[j]])),
  }))
  return { columns, rows }
}

export function sortRows<T extends { cells: Record<string, any> }>(rows: T[], sort: { key: string; dir: 'asc' | 'desc' } | null | undefined): T[] {
  if (!sort) return rows
  const { key, dir } = sort
  const m = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const x = a.cells[key], y = b.cells[key]
    if (x == null && y == null) return 0
    if (x == null) return 1
    if (y == null) return -1
    if (typeof x === 'number' && typeof y === 'number') return (x - y) * m
    return String(x).localeCompare(String(y), 'pt-BR', { numeric: true }) * m
  })
}

export function useSort(initial: { key: string; dir: 'asc' | 'desc' } | null = null) {
  const [sort, setSort] = useState(initial)
  const toggle = (key: string) => setSort((s) => (s?.key === key ? (s.dir === 'desc' ? { key, dir: 'asc' } : null) : { key, dir: 'desc' }))
  return [sort, toggle, setSort] as const
}
