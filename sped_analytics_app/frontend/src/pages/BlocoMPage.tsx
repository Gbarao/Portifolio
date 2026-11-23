import { AlertTriangle, BadgePercent, Building2, CalendarRange, CheckCircle2, Coins, FileSpreadsheet, HandCoins, Info, Landmark, PiggyBank, Receipt, RefreshCw, Scale, XCircle } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { DataGrid, sortRows, useSort, type GridCol, type GridRow } from '../components/DataGrid'
import { FilterButton, MultiList } from '../components/FilterBar'
import { CollapseToggle, MaxBackdrop, MaxButton, useCollapsed, useDragHeight, useMaximize } from '../components/layout'
import { Badge, Button, Card, Empty, Kpi, Segmented, Select, Spinner, Switch, Tip, cx } from '../components/ui'
import { api, waitJob } from '../lib/api'
import { runExport } from '../lib/exporting'
import { fmtBRL, fmtCnpj, fmtComp, fmtInt, fmtMoney } from '../lib/format'
import { useApp } from '../lib/store'
import type { BlocoMState, ColType, Table, Tributo } from '../lib/types'

interface Overview {
  arquivos: { id_arquivo: number; competencia: string; cnpj: string; nome: string; indexado: boolean; linhas_m: number }[]
  empresas: { cnpj: string; nome: string; competencias: string[] }[]
  competencias: string[]; pendentes: number; sem_bloco_m: number
}
type Sections = Record<string, Table>
interface Result {
  sections: Sections; labels: Record<string, string>; divergencias: number; arquivos: number; ms: number
  kpis: Record<Tributo, Record<string, number>>
  leiaute: { reg: string; linhas: number; campos_encontrados: number[]; campos_esperados: number[] }[]
}

const TABS = [
  { value: 'resumo', label: 'Apuração' }, { value: 'creditos', label: 'Créditos' }, { value: 'contribuicao', label: 'Contribuição' },
  { value: 'ajustes', label: 'Ajustes' }, { value: 'receitas', label: 'Receitas não tributadas' }, { value: 'saldos', label: 'Saldos de créditos' },
  { value: 'conferencia', label: 'Conferência com documentos' }, { value: 'verificacoes', label: 'Verificações' },
]
const HIDE = new Set(['tributo', 'file_id', 'doc_line', 'parent_line', 'nome_empresa'])

/** Linhas de uma seção, filtradas pelo tributo. */
function rowsOf(sec: Table | undefined, tributo?: Tributo): Record<string, any>[] {
  if (!sec) return []
  const ti = sec.columns.indexOf('tributo')
  return sec.rows.filter((r) => !tributo || ti < 0 || r[ti] === tributo).map((r) => Object.fromEntries(sec.columns.map((c, j) => [c, r[j]])))
}

export function BlocoMPage() {
  const { state, set, dataVersion } = useApp()
  const bs = state.blocom
  const upd = useCallback((p: Partial<BlocoMState>) => set((s) => ({ blocom: { ...s.blocom, ...p } })), [set])
  const [ov, setOv] = useState<Overview | null>(null)
  const [res, setRes] = useState<Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [indexing, setIndexing] = useState<string | null>(null)
  const loadOv = useCallback(() => api.get<Overview>('/api/blocom/overview').then(setOv).catch((e) => toast.error(e.message)), [])
  useEffect(() => { loadOv() }, [loadOv, dataVersion])
  const body = useMemo(() => ({ empresas: bs.empresas, comp_ini: bs.comp_ini, comp_fim: bs.comp_fim }), [bs.empresas, bs.comp_ini, bs.comp_fim])
  const key = JSON.stringify(body) + dataVersion + (ov?.pendentes ?? '')
  useEffect(() => {
    let alive = true
    setLoading(true)
    api.post<Result>('/api/blocom/query', body).then((r) => alive && setRes(r)).catch((e) => toast.error(e.message)).finally(() => alive && setLoading(false))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const [kpiCollapsed, setKpiCollapsed] = useCollapsed('blocom-kpis')

  const runIndex = async () => {
    setIndexing('Iniciando…')
    try {
      const { job } = await api.post('/api/raw/index')
      const j = await waitJob(job, (x) => setIndexing(`${x.msg} · ${Math.round(x.frac * 100)}%`))
      if (j.status === 'error') toast.error(j.error || 'Falha')
      else toast.success(`${j.result.indexados} arquivo(s) indexado(s)`)
      await loadOv()
    } catch (e: any) { toast.error(e.message) } finally { setIndexing(null) }
  }

  if (ov && ov.arquivos.length === 0) {
    return (
      <div className="p-5"><Card><Empty icon={<Receipt className="h-6 w-6" />} title="Nenhuma EFD-Contribuições importada">
        Importe os arquivos na tela <button className="font-medium text-accent underline" onClick={() => set({ page: 'arquivos' })}>Arquivos</button>.
      </Empty></Card></div>
    )
  }
  const comps = ov?.competencias ?? []
  const empOpts = (ov?.empresas ?? []).map((e) => [e.cnpj, `${e.nome} (${e.competencias.length} mês(es))`] as [string, string])
  const k = res?.kpis?.[bs.tributo]
  const T = bs.tributo === 'PIS' ? 'PIS/Pasep' : 'Cofins'

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-auto p-3 tall:gap-3 tall:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <FilterButton icon={<Building2 className="h-4 w-4" />} label="Empresa" count={bs.empresas.length}
          summary={bs.empresas.length === 1 ? (empOpts.find((e) => e[0] === bs.empresas[0])?.[1] ?? fmtCnpj(bs.empresas[0])) : bs.empresas.length ? `${bs.empresas.length} empresas` : undefined}>
          <MultiList options={empOpts} value={bs.empresas} onChange={(v) => upd({ empresas: v })} format={fmtCnpj} />
        </FilterButton>
        <div className="flex h-[34px] items-center gap-1 rounded-lg border bg-panel pl-2 pr-0.5 text-[12.5px]">
          <CalendarRange className="h-4 w-4 text-muted" />
          <Select className="border-0" value={bs.comp_ini || ''} onChange={(e) => upd({ comp_ini: e.target.value || undefined })}>
            <option value="">Início</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
          </Select>
          <span className="text-muted">a</span>
          <Select className="border-0" value={bs.comp_fim || ''} onChange={(e) => upd({ comp_fim: e.target.value || undefined })}>
            <option value="">Fim</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
          </Select>
        </div>
        <Segmented value={bs.tributo} onChange={(t) => upd({ tributo: t })} options={[{ value: 'PIS', label: 'PIS/Pasep' }, { value: 'COFINS', label: 'Cofins' }]} />
        <div className="flex-1" />
        {loading ? <Spinner /> : res && <span className="text-[12px] text-muted">{res.arquivos} arquivo(s) · {res.ms} ms</span>}
        <CollapseToggle collapsed={kpiCollapsed} onToggle={() => setKpiCollapsed(!kpiCollapsed)} label="indicadores" />
        <Button variant="primary" icon={<FileSpreadsheet className="h-4 w-4" />} onClick={() => runExport('/api/export/blocom', body, 'Excel do Bloco M')}>Excel</Button>
      </div>

      {ov && ov.pendentes > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12.5px]">
          <RefreshCw className="h-4 w-4 shrink-0 text-warn" />
          <span className="flex-1">{ov.pendentes} arquivo(s) foram importados antes de o programa guardar as linhas originais; o Bloco M deles só aparece depois de indexados.</span>
          {indexing ? <span className="flex items-center gap-2 text-muted"><Spinner />{indexing}</span> : <Button size="sm" variant="primary" onClick={runIndex}>Indexar agora</Button>}
        </div>
      )}
      {ov && ov.sem_bloco_m > 0 && <div className="flex items-center gap-2 text-[12.5px] text-muted"><Info className="h-4 w-4" />{ov.sem_bloco_m} arquivo(s) sem registros de apuração no Bloco M (escrituração sem movimento ou só com o Bloco M aberto).</div>}
      {res && res.leiaute.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12.5px]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <span>Leiaute diferente do esperado: {res.leiaute.map((w) => `${w.reg} (${w.linhas} linha(s) com ${w.campos_encontrados.join('/')} campos; esperado ${w.campos_esperados.join(' ou ')})`).join('; ')}.
            Os valores dessas linhas podem estar em campos deslocados — confira na tela EFD-Contribuições (linha original).</span>
        </div>
      )}

      {!kpiCollapsed && (
        <div className="grid shrink-0 grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-6">
          <Kpi label={`${T} apurado`} icon={<Landmark className="h-3.5 w-3.5" />} loading={!res} value={fmtBRL(k?.contribuicao)}
            hint={k ? `não cumulativo ${fmtMoney(k.contribuicao_nc)} · cumulativo ${fmtMoney(k.contribuicao_cum)}` : undefined} />
          <Kpi label="Créditos apurados" icon={<HandCoins className="h-3.5 w-3.5" />} tone="text-ok" loading={!res} value={fmtBRL(k?.creditos_apurados)}
            hint={k ? `ajustes ${fmtMoney(k.ajustes_credito)} · disponível ${fmtMoney(k.creditos_disponiveis)}` : undefined} />
          <Kpi label="Créditos descontados" icon={<BadgePercent className="h-3.5 w-3.5" />} loading={!res} value={fmtBRL(k ? k.creditos_descontados + k.creditos_anteriores : null)}
            hint={k ? `do período ${fmtMoney(k.creditos_descontados)} · anteriores ${fmtMoney(k.creditos_anteriores)}` : undefined} />
          <Kpi label="Retenções e deduções" icon={<Coins className="h-3.5 w-3.5" />} loading={!res} value={fmtBRL(k ? k.retencoes + k.outras_deducoes : null)}
            hint={k ? `retenções ${fmtMoney(k.retencoes)} · outras ${fmtMoney(k.outras_deducoes)}` : undefined} />
          <Kpi label="A recolher" icon={<Receipt className="h-3.5 w-3.5" />} tone="text-bad" loading={!res} value={fmtBRL(k?.a_recolher)} />
          <Tip content="Último período selecionado de cada empresa: saldo dos créditos do próprio mês (M100/M500) + saldo final de créditos de períodos anteriores (1100/1500)">
            <div><Kpi label="Saldo de créditos" icon={<PiggyBank className="h-3.5 w-3.5" />} loading={!res} value={fmtBRL(k?.saldo_credito)} hint="a utilizar em períodos futuros" /></div>
          </Tip>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={bs.tab as any} onChange={(tab) => upd({ tab })} options={TABS.map((t) => ({
          ...t, label: t.value === 'verificacoes' && res ? `${t.label}${res.divergencias ? ` (${res.divergencias})` : ''}` : t.label,
        }))} />
        {res && res.divergencias > 0 && <Badge tone="bad"><XCircle className="h-3 w-3" />{res.divergencias} divergência(s) nas verificações</Badge>}
        {res && res.divergencias === 0 && res.arquivos > 0 && <Badge tone="ok"><CheckCircle2 className="h-3 w-3" />verificações aritméticas sem divergência</Badge>}
      </div>

      <div className="flex min-h-[420px] flex-1 flex-col">
        {!res ? <div className="skeleton h-full min-h-[300px] rounded-xl" /> : (
          <>
            {bs.tab === 'resumo' && <Demonstrativo res={res} tributo={bs.tributo} />}
            {bs.tab === 'creditos' && <MasterDetail res={res} tributo={bs.tributo} master="credito" detail="base_credito" link="doc_line"
              masterTitle={`Créditos do período (${bs.tributo === 'PIS' ? 'M100' : 'M500'})`} detailTitle={`Base de cálculo por natureza e CST (${bs.tributo === 'PIS' ? 'M105' : 'M505'})`}
              hint="Clique em um crédito para ver só a base dele" />}
            {bs.tab === 'contribuicao' && <Stack res={res} tributo={bs.tributo} items={[
              { key: 'contribuicao', title: `Contribuição por código (${bs.tributo === 'PIS' ? 'M210' : 'M610'})` },
              { key: 'cod_receita', title: `Débitos por código de receita (${bs.tributo === 'PIS' ? 'M205' : 'M605'})` }]} />}
            {bs.tab === 'ajustes' && <MasterDetail res={res} tributo={bs.tributo} master="ajustes" detail="det_ajustes" link="parent_line"
              masterTitle="Ajustes de crédito, de base de cálculo e da contribuição" detailTitle="Detalhamento dos ajustes (M115/M225/M515/M625)"
              hint="Clique em um ajuste para ver o detalhamento" empty="Nenhum ajuste informado no período" />}
            {bs.tab === 'receitas' && <MasterDetail res={res} tributo={bs.tributo} master="receita_nt" detail="receita_nt_det" link="doc_line"
              masterTitle={`Receitas isentas, não alcançadas, alíquota zero ou suspensão (${bs.tributo === 'PIS' ? 'M400' : 'M800'})`}
              detailTitle={`Detalhamento por natureza da receita (${bs.tributo === 'PIS' ? 'M410' : 'M810'})`} hint="Clique em um CST para filtrar o detalhamento"
              empty="Nenhuma receita não tributada informada" />}
            {bs.tab === 'saldos' && <Stack res={res} tributo={bs.tributo} items={[{ key: 'saldo', title: `Controle de créditos de períodos anteriores (${bs.tributo === 'PIS' ? '1100' : '1500'})`,
              empty: 'Nenhum registro 1100/1500 no período (não há créditos de períodos anteriores controlados)' }]} />}
            {bs.tab === 'conferencia' && <Conferencia res={res} tributo={bs.tributo} />}
            {bs.tab === 'verificacoes' && <Verificacoes res={res} tributo={bs.tributo} />}
          </>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------
function gridOf(sec: Table | undefined, labels: Record<string, string>, rows: Record<string, any>[], opts: { widths?: Record<string, number>; render?: Record<string, (r: GridRow) => ReactNode> } = {}) {
  if (!sec) return { columns: [] as GridCol[], rows: [] as GridRow[] }
  const columns: GridCol[] = sec.columns.filter((c) => !HIDE.has(c)).map((c, i) => ({
    key: c, label: labels[c] ?? c, type: (c === 'line_no' ? 'text' : sec.types[sec.columns.indexOf(c)]) as ColType,
    width: opts.widths?.[c] ?? (/(_desc|descr|desc_compl|verificacao|info_compl)$/.test(c) ? 280 : c === 'competencia' ? 100 : c === 'cnpj_empresa' ? 150 : undefined),
    sticky: i === 0, render: opts.render?.[c] ?? (c === 'competencia' ? (r: GridRow) => fmtComp(r.cells.competencia) : undefined),
  }))
  return { columns, rows: rows.map((r, i) => ({ id: `${r.file_id}:${r.line_no ?? i}`, cells: r })) }
}

function totalsOf(cols: GridCol[], rows: GridRow[]) {
  const o: Record<string, number> = {}
  cols.forEach((c) => { if (c.type === 'money') o[c.key] = rows.reduce((a, r) => a + (Number(r.cells[c.key]) || 0), 0) })
  return o
}

function GridCard({ title, sub, grid, totals, selectedId, onSelect, actions, empty, className }:
  { title: string; sub?: ReactNode; grid: { columns: GridCol[]; rows: GridRow[] }; totals?: boolean; selectedId?: string | null; onSelect?: (r: GridRow) => void; actions?: ReactNode; empty?: string; className?: string }) {
  const mx = useMaximize()
  const [sort, toggleSort] = useSort(null)
  const tot = useMemo(() => (totals && grid.rows.length > 1 ? totalsOf(grid.columns, grid.rows) : null), [grid, totals])
  return (
    <>
      <MaxBackdrop on={mx.on} onClose={mx.toggle} />
      <Card className={cx('flex min-h-0 flex-col', className, mx.cls)}>
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
          <span className="text-[13px] font-semibold">{title}</span>
          <span className="text-[12px] text-muted">{fmtInt(grid.rows.length)} linha(s){sub ? <> · {sub}</> : null}</span>
          <div className="flex-1" />{actions}<MaxButton on={mx.on} onClick={mx.toggle} size="icon-sm" />
        </div>
        <div className="min-h-0 flex-1 p-2">
          <DataGrid columns={grid.columns} rows={sortRows(grid.rows, sort)} totals={tot} dense rowHeight={32} sort={sort} onSort={toggleSort}
            selectedId={selectedId} onSelect={onSelect} emptyText={empty ?? 'Nenhum registro'} />
        </div>
      </Card>
    </>
  )
}

function Stack({ res, tributo, items }: { res: Result; tributo: Tributo; items: { key: string; title: string; empty?: string }[] }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {items.map((it) => {
        const g = gridOf(res.sections[it.key], res.labels, rowsOf(res.sections[it.key], tributo))
        return <GridCard key={it.key} title={it.title} grid={g} totals empty={it.empty} className="min-h-[220px] flex-1" />
      })}
    </div>
  )
}

function MasterDetail({ res, tributo, master, detail, link, masterTitle, detailTitle, hint, empty }:
  { res: Result; tributo: Tributo; master: string; detail: string; link: string; masterTitle: string; detailTitle: string; hint: string; empty?: string }) {
  const [sel, setSel] = useState<GridRow | null>(null)
  useEffect(() => setSel(null), [tributo, res])
  const gm = useMemo(() => gridOf(res.sections[master], res.labels, rowsOf(res.sections[master], tributo)), [res, master, tributo])
  const det = useMemo(() => {
    let rows = rowsOf(res.sections[detail], tributo)
    if (sel) rows = rows.filter((r) => r.file_id === sel.cells.file_id && r[link] === sel.cells.line_no)
    return gridOf(res.sections[detail], res.labels, rows)
  }, [res, detail, tributo, sel, link])
  const { h, handle } = useDragHeight(`blocom-${master}`, 300)
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <GridCard title={masterTitle} sub={hint} grid={gm} totals selectedId={sel?.id} onSelect={(r) => setSel((s) => (s?.id === r.id ? null : r))} empty={empty} className="min-h-[200px] flex-1" />
      {handle}
      <div className="flex shrink-0 flex-col" style={{ height: h }}>
        <GridCard title={detailTitle} sub={sel ? 'filtrado pela linha selecionada' : 'todas as linhas'} grid={det} totals className="flex-1"
          actions={sel ? <Button size="sm" variant="ghost" onClick={() => setSel(null)}>Mostrar todas</Button> : undefined} />
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------
const DEMO: { key: string; label: string; strong?: boolean; sign?: string }[] = [
  { key: 'vl_tot_cont_nc_per', label: 'Contribuição não cumulativa do período' },
  { key: 'vl_tot_cred_desc', label: 'Créditos descontados – apurados no período', sign: '−' },
  { key: 'vl_tot_cred_desc_ant', label: 'Créditos descontados – de períodos anteriores', sign: '−' },
  { key: 'vl_tot_cont_nc_dev', label: 'Contribuição não cumulativa devida', strong: true, sign: '=' },
  { key: 'vl_ret_nc', label: 'Retenções na fonte', sign: '−' },
  { key: 'vl_out_ded_nc', label: 'Outras deduções', sign: '−' },
  { key: 'vl_cont_nc_rec', label: 'Não cumulativa a recolher', strong: true, sign: '=' },
  { key: 'vl_tot_cont_cum_per', label: 'Contribuição cumulativa do período' },
  { key: 'vl_ret_cum', label: 'Retenções na fonte (cumulativa)', sign: '−' },
  { key: 'vl_out_ded_cum', label: 'Outras deduções (cumulativa)', sign: '−' },
  { key: 'vl_cont_cum_rec', label: 'Cumulativa a recolher', strong: true, sign: '=' },
  { key: 'vl_tot_cont_rec', label: 'TOTAL A RECOLHER', strong: true, sign: '=' },
]

function Demonstrativo({ res, tributo }: { res: Result; tributo: Tributo }) {
  const rows = rowsOf(res.sections.consolidacao, tributo)
  const comps = [...new Set(rows.map((r) => r.competencia as string))].sort()
  const val = (c: string | null, k: string) => rows.filter((r) => c == null || r.competencia === c).reduce((a, r) => a + (Number(r[k]) || 0), 0)
  const cred = rowsOf(res.sections.credito, tributo)
  const chart = comps.map((c) => ({ c, cont: val(c, 'vl_tot_cont_nc_per') + val(c, 'vl_tot_cont_cum_per'), desc: val(c, 'vl_tot_cred_desc') + val(c, 'vl_tot_cred_desc_ant'), rec: val(c, 'vl_tot_cont_rec'),
    apur: cred.filter((r) => r.competencia === c).reduce((a, r) => a + (Number(r.vl_cred) || 0), 0) }))
  const max = Math.max(1, ...chart.map((d) => Math.max(d.cont, d.apur)))
  const mx = useMaximize()
  if (!rows.length) return <Card className="flex-1"><Empty icon={<Scale className="h-6 w-6" />} title={`Nenhum ${tributo === 'PIS' ? 'M200' : 'M600'} no período`}>A escrituração selecionada não tem a consolidação da contribuição no Bloco M.</Empty></Card>
  return (
    <>
      <MaxBackdrop on={mx.on} onClose={mx.toggle} />
      <Card className={cx('flex min-h-0 flex-1 flex-col', mx.cls)}>
        <div className="flex flex-wrap items-center gap-3 border-b px-4 py-2">
          <span className="text-[13px] font-semibold">Demonstrativo da apuração ({tributo === 'PIS' ? 'M200' : 'M600'}) por competência</span>
          <span className="flex items-center gap-3 text-[11.5px] text-muted">
            <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-accent/60" />Contribuição</span>
            <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-ok/70" />Crédito apurado</span>
            <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-bad/60" />A recolher</span>
          </span>
          <div className="flex-1" /><MaxButton on={mx.on} onClick={mx.toggle} size="icon-sm" />
        </div>
        <div className="flex h-[96px] shrink-0 items-end gap-3 overflow-x-auto px-4 pt-3">
          {chart.map((d) => (
            <Tip key={d.c} content={<span>{fmtComp(d.c)} · contribuição {fmtBRL(d.cont)} · crédito apurado {fmtBRL(d.apur)} · a recolher {fmtBRL(d.rec)}</span>}>
              <div className="flex h-full min-w-[42px] max-w-[90px] flex-1 items-end gap-[2px]">
                <div className="flex-1 rounded-t bg-accent/55" style={{ height: `${Math.max(2, (d.cont / max) * 100)}%` }} />
                <div className="flex-1 rounded-t bg-ok/70" style={{ height: `${Math.max(2, (d.apur / max) * 100)}%` }} />
                <div className="flex-1 rounded-t bg-bad/60" style={{ height: `${Math.max(2, (d.rec / max) * 100)}%` }} />
              </div>
            </Tip>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-2">
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="sticky top-0 z-[2] bg-sunken/95 backdrop-blur">
              <tr>
                <th className="sticky left-0 z-[3] min-w-[300px] bg-sunken px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted">Linha do demonstrativo</th>
                {comps.map((c) => <th key={c} className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-muted">{fmtComp(c)}</th>)}
                {comps.length > 1 && <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-fg">Total</th>}
              </tr>
            </thead>
            <tbody>
              {DEMO.map((d) => (
                <tr key={d.key} className={cx('border-b border-line/60', d.strong && 'bg-sunken/50 font-semibold', d.key === 'vl_tot_cont_rec' && 'bg-accent/10')}>
                  <td className="sticky left-0 z-[1] bg-inherit px-3 py-1.5"><span className="inline-block w-4 text-muted">{d.sign}</span>{d.label}
                    <span className="ml-1.5 font-mono text-[10.5px] font-normal text-muted">{d.key.toUpperCase()}</span></td>
                  {comps.map((c) => <td key={c} className="num whitespace-nowrap px-3 py-1.5 text-right">{fmtMoney(val(c, d.key))}</td>)}
                  {comps.length > 1 && <td className="num whitespace-nowrap px-3 py-1.5 text-right font-semibold">{fmtMoney(val(null, d.key))}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 pt-3 text-[12px] text-muted">Valores como informados no {tributo === 'PIS' ? 'M200' : 'M600'}, somados entre as empresas selecionadas. As verificações conferem cada linha com os registros que a compõem.</p>
        </div>
      </Card>
    </>
  )
}

function Conferencia({ res, tributo }: { res: Result; tributo: Tributo }) {
  const [onlyDiff, setOnlyDiff] = useState(false)
  const money = (k: string) => (r: GridRow) => {
    const v = Number(r.cells[k]) || 0
    return <span className={cx('num', Math.abs(v) > 0.009 ? 'font-semibold text-bad' : 'text-ok')}>{fmtMoney(v)}</span>
  }
  const resumo = useMemo(() => gridOf(res.sections.conferencia_resumo, res.labels, rowsOf(res.sections.conferencia_resumo, tributo),
    { render: { diferenca_base: money('diferenca_base'), diferenca_credito: money('diferenca_credito') } }), [res, tributo]) // eslint-disable-line react-hooks/exhaustive-deps
  const det = useMemo(() => {
    let rows = rowsOf(res.sections.conferencia, tributo)
    if (onlyDiff) rows = rows.filter((r) => Math.abs(Number(r.diferenca) || 0) > 0.009)
    return gridOf(res.sections.conferencia, res.labels, rows, { render: { diferenca: money('diferenca') } })
  }, [res, tributo, onlyDiff]) // eslint-disable-line react-hooks/exhaustive-deps
  const { h, handle } = useDragHeight('blocom-conf', 360)
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 flex items-start gap-2 rounded-lg border bg-panel px-3 py-2 text-[12.5px] text-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <span>Compara a base de cálculo do crédito informada no {tributo === 'PIS' ? 'M105' : 'M505'} (CST 50 a 56 e 60 a 66) com a soma dos documentos da mesma escrituração:
          C170, A170, C191/C195, C501/C505, D101/D105, D501/D505, F100, F120 e F130 (documentos cancelados excluídos). No C170 e no C191/C195 a natureza
          da base é derivada do CFOP (a coluna “Base com natureza derivada do CFOP” mostra quanto). Não entram: C395/C396, F150 (estoque de abertura),
          F200 a F211 (atividade imobiliária) e créditos extemporâneos (1101/1501) — diferenças nessas naturezas podem ser explicadas por eles.
          Para CST 53 a 56 e 63 a 66 a base total, que se repete em cada tipo de crédito, é contada uma vez.</span>
      </div>
      <GridCard title="Resumo por competência" grid={resumo} totals className="min-h-[160px] flex-1" />
      {handle}
      <div className="flex shrink-0 flex-col" style={{ height: h }}>
        <GridCard title="Por natureza da base e CST" grid={det} totals className="flex-1"
          actions={<Switch checked={onlyDiff} onChange={setOnlyDiff} label="Só diferenças" />} />
      </div>
    </div>
  )
}

function Verificacoes({ res, tributo }: { res: Result; tributo: Tributo }) {
  const [onlyDiv, setOnlyDiv] = useState(false)
  const g = useMemo(() => {
    let rows = rowsOf(res.sections.verificacoes, tributo)
    if (onlyDiv) rows = rows.filter((r) => r.status !== 'OK')
    return gridOf(res.sections.verificacoes, res.labels, rows, {
      widths: { verificacao: 520, status: 110 },
      render: { status: (r) => r.cells.status === 'OK' ? <Badge tone="ok"><CheckCircle2 className="h-3 w-3" />OK</Badge> : <Badge tone="bad"><XCircle className="h-3 w-3" />Divergente</Badge> },
    })
  }, [res, tributo, onlyDiv])
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-start gap-2 rounded-lg border bg-panel px-3 py-2 text-[12.5px] text-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <span>Conferências aritméticas entre os registros da própria escrituração (ex.: total a recolher do M200 = não cumulativa + cumulativa;
          crédito descontado = soma dos M100; saldos do 1100). O PVA da Receita valida a maior parte delas na transmissão — uma divergência aqui indica
          arquivo editado fora do PVA ou retificação incompleta. Tolerância de R$ 0,01.</span>
      </div>
      <GridCard title="Verificações" grid={g} className="min-h-[300px] flex-1" actions={<Switch checked={onlyDiv} onChange={setOnlyDiv} label="Só divergências" />} />
    </div>
  )
}
