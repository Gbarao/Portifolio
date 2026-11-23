import { useMemo, useState, type ReactNode } from 'react'
import { fmtCell, isNumeric } from '../lib/format'
import type { ColType, Table } from '../lib/types'
import { cx } from './ui'

export interface MiniCol { key: string; label: string; type?: ColType; render?: (row: Record<string, any>) => ReactNode; className?: string }

/** Tabela compacta de altura automática (resumos com poucas linhas), com ordenação e linha de total. */
export function MiniTable({ cols, rows, total, maxH = 300, empty = 'Sem dados', onRow, selected }:
  { cols: MiniCol[]; rows: Record<string, any>[]; total?: boolean; maxH?: number | string; empty?: ReactNode; onRow?: (r: Record<string, any>) => void; selected?: (r: Record<string, any>) => boolean }) {
  const [sort, setSort] = useState<{ k: string; d: 1 | -1 } | null>(null)
  const sorted = useMemo(() => {
    if (!sort) return rows
    return [...rows].sort((a, b) => {
      const x = a[sort.k], y = b[sort.k]
      if (x == null) return 1
      if (y == null) return -1
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'pt-BR', { numeric: true })) * sort.d
    })
  }, [rows, sort])
  const sums = useMemo(() => {
    if (!total) return null
    const o: Record<string, number> = {}
    cols.forEach((c) => { if (c.type && ['money', 'int', 'qty'].includes(c.type)) o[c.key] = rows.reduce((a, r) => a + (Number(r[c.key]) || 0), 0) })
    return o
  }, [rows, cols, total])
  return (
    <div className="overflow-auto" style={{ maxHeight: maxH }}>
      <table className="w-full border-collapse text-[12.5px]">
        <thead className="sticky top-0 z-[1] bg-sunken/95 backdrop-blur">
          <tr>
            {cols.map((c) => (
              <th key={c.key} onClick={() => setSort((s) => (s?.k === c.key ? (s.d === -1 ? { k: c.key, d: 1 } : null) : { k: c.key, d: -1 }))}
                className={cx('cursor-pointer select-none whitespace-nowrap border-b px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted hover:text-fg',
                  c.type && isNumeric(c.type) ? 'text-right' : 'text-left')}>
                {c.label}{sort?.k === c.key ? (sort.d === -1 ? ' ↓' : ' ↑') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && <tr><td colSpan={cols.length} className="px-3 py-6 text-center text-muted">{empty}</td></tr>}
          {sorted.map((r, i) => (
            <tr key={i} onClick={onRow ? () => onRow(r) : undefined}
              className={cx('border-b border-line/60 last:border-0', onRow && 'cursor-pointer hover:bg-sunken/70', selected?.(r) && 'bg-accent/10')}>
              {cols.map((c) => (
                <td key={c.key} className={cx('px-2.5 py-1.5', c.type && isNumeric(c.type) ? 'num whitespace-nowrap text-right' : '', c.className)}>
                  {c.render ? c.render(r) : fmtCell(r[c.key], c.type ?? 'text', c.key)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {sums && sorted.length > 1 && (
          <tfoot className="sticky bottom-0 bg-sunken/95 font-semibold backdrop-blur">
            <tr>{cols.map((c, j) => (
              <td key={c.key} className={cx('border-t-2 px-2.5 py-1.5', c.type && isNumeric(c.type) && 'num whitespace-nowrap text-right')}>
                {j === 0 ? 'Total' : c.key in sums ? fmtCell(sums[c.key], c.type!) : ''}
              </td>))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

export const tableRows = (t: Table | null | undefined): Record<string, any>[] =>
  t ? t.rows.map((r) => Object.fromEntries(t.columns.map((c, j) => [c, r[j]]))) : []

export const typeOf = (t: Table | null | undefined, c: string): ColType => (t ? t.types[t.columns.indexOf(c)] ?? 'text' : 'text')
