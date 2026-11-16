import { AlertCircle, ArrowDownToLine, CheckCircle2, Info, PlayCircle, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { DataGrid, sortRows, tableToGrid, useSort } from '../components/DataGrid'
import { Button, Card, Input, Spinner, cx } from '../components/ui'
import { api, download } from '../lib/api'
import { fmtInt } from '../lib/format'
import { useApp } from '../lib/store'
import type { Table } from '../lib/types'

const GROUPS: [string, string[]][] = [
  ['Integridade do cruzamento', ['fechamento_efd', 'efd_sem_par', 'qualidade_cruzamento']],
  ['SPED Fiscal × EFD-Contribuições', ['valor_documento', 'valor_item', 'ec_sem_sf', 'item_sem_c190']],
  ['Coerência tributária', ['credito_icms_sem_pis', 'credito_pis_sem_icms', 'cst_divergente_filiais']],
]

export function AuditPage() {
  const { meta, state, dataVersion } = useApp()
  const [tol, setTol] = useState(String(meta.tolerancia))
  const [counts, setCounts] = useState<Record<string, any>>({})
  const [running, setRunning] = useState(false)
  const [current, setCurrent] = useState<string | null>(null)
  const [data, setData] = useState<(Table & { label: string; total: number }) | null>(null)
  const [loading, setLoading] = useState(false)
  const [sort, toggleSort] = useSort(null)
  const checks = Object.fromEntries(meta.checks.map((c) => [c.key, c]))

  const runAll = async () => {
    setRunning(true)
    try {
      const r = await api.post('/api/audit/summary', { gf: state.gf })
      setCounts(Object.fromEntries(r.items.map((i: any) => [i.verificacao, i.ocorrencias])))
    } catch (e: any) { toast.error(e.message) } finally { setRunning(false) }
  }
  useEffect(() => { runAll() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [JSON.stringify(state.gf), dataVersion])

  const open = async (k: string) => {
    setCurrent(k); setLoading(true); setData(null)
    try { setData(await api.post('/api/audit/check', { check: k, gf: state.gf, tol: Number(tol.replace(',', '.')) })) }
    catch (e: any) { toast.error(e.message) } finally { setLoading(false) }
  }
  const exp = async (all: boolean) => {
    const id = toast.loading('Gerando Excel…')
    try {
      const r = await api.post('/api/export/audit', { gf: state.gf, tol: Number(tol.replace(',', '.')), check: all ? null : current })
      toast.success('Relatório de auditoria pronto', { id, description: r.path }); download(r.url)
    } catch (e: any) { toast.error(e.message, { id }) }
  }

  const g = useMemo(() => tableToGrid(data, { sticky: 2 }), [data])
  const totals = useMemo(() => {
    if (!data || !current || checks[current]?.informative) return null
    const out: Record<string, number> = {}
    data.columns.forEach((c, j) => { if (data.types[j] === 'money') out[c] = data.rows.reduce((a, r) => a + (Number(r[j]) || 0), 0) })
    return out
  }, [data, current])
  const filtersActive = Object.keys(state.gf).length > 0

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1 text-[12.5px] text-muted">
          {filtersActive ? 'Considera o período e as filiais dos filtros da Análise.' : 'Considera toda a base (sem filtros na Análise).'}
        </div>
        <label className="flex items-center gap-2 text-[12.5px] text-muted">Tolerância R$<Input className="w-24" value={tol} onChange={(e) => setTol(e.target.value)} /></label>
        <Button icon={<PlayCircle className="h-4 w-4" />} loading={running} onClick={runAll}>Executar verificações</Button>
        <Button variant="primary" icon={<ArrowDownToLine className="h-4 w-4" />} onClick={() => exp(true)}>Exportar todas</Button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {GROUPS.map(([title, keys]) => (
          <Card key={title} className="p-2">
            <div className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
            {keys.filter((k) => checks[k]).map((k) => {
              const n = counts[k]
              const info = checks[k].informative
              const okState = !info && n === 0
              const bad = !info && typeof n === 'number' && n > 0
              return (
                <button key={k} onClick={() => open(k)}
                  className={cx('flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-sunken', current === k && 'bg-accent/[0.07] ring-1 ring-accent/30')}>
                  <span className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                    info ? 'bg-info/10 text-info' : okState ? 'bg-ok/10 text-ok' : bad ? 'bg-bad/10 text-bad' : 'bg-sunken text-muted')}>
                    {running && n === undefined ? <Spinner /> : info ? <Info className="h-4 w-4" /> : okState ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                  </span>
                  <span className="min-w-0 flex-1 text-[12.5px] leading-snug">{checks[k].label}</span>
                  {!info && <span className={cx('num text-[15px] font-semibold', bad ? 'text-bad' : 'text-muted')}>{typeof n === 'number' ? fmtInt(n) : '—'}</span>}
                </button>
              )
            })}
          </Card>
        ))}
      </div>

      <Card className="flex min-h-[360px] flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-4 py-2.5">
          <ShieldCheck className="h-4 w-4 text-muted" />
          <div className="min-w-0 flex-1 truncate text-[13px] font-semibold">
            {current ? checks[current].label : 'Selecione uma verificação'}
            {data && <span className="ml-2 font-normal text-muted">· {fmtInt(data.total)} linha(s){data.total > data.rows.length ? ` (exibindo ${fmtInt(data.rows.length)})` : ''}</span>}
          </div>
          {current && <Button size="sm" icon={<ArrowDownToLine className="h-3.5 w-3.5" />} onClick={() => exp(false)}>Excel</Button>}
        </div>
        <div className="min-h-0 flex-1 p-2">
          {current ? <DataGrid columns={g.columns} rows={sortRows(g.rows, sort)} totals={totals} loading={loading} dense sort={sort} onSort={toggleSort}
            emptyText={<span className="flex items-center gap-2 text-ok"><CheckCircle2 className="h-4 w-4" />Nenhuma ocorrência</span>} />
            : <div className="flex h-full items-center justify-center text-[13px] text-muted">Clique em uma verificação acima para ver o detalhe.</div>}
        </div>
      </Card>
    </div>
  )
}
