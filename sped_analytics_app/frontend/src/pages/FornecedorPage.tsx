import { ArrowDownToLine, BadgePercent, Building2, CalendarRange, Coins, FileSpreadsheet, FileText, History, Landmark, Loader2, Receipt, Search, UserSearch, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { DataGrid, sortRows, tableToGrid, useSort } from '../components/DataGrid'
import { MaxBackdrop, MaxButton, SidePanel, useCollapsed, useMaximize, CollapseToggle } from '../components/layout'
import { IndexBanner } from '../components/IndexBanner'
import { MiniTable, tableRows, typeOf, type MiniCol } from '../components/MiniTable'
import { Badge, Button, Card, Empty, Input, Kpi, Segmented, Select, Spinner, Tip, cx } from '../components/ui'
import { api } from '../lib/api'
import { runExport } from '../lib/exporting'
import { fmtBRL, fmtCnpj, fmtComp, fmtInt } from '../lib/format'
import { useApp } from '../lib/store'
import type { FornRef, FornState, RawTipo, Table } from '../lib/types'
import { DimCell, DocsPanel } from './AnalysisPage'
import { exportTo, toGrid, useInfinite } from './RawPage'

interface Sug { cnpj_cpf: string; razao_social: string | null; uf: string | null; ultima_competencia: string | null; vl_contabil: number | null; pis_cofins: number | null; tem_entradas: boolean }
interface Prof {
  cnpjs: string[]; cadastro: Table | null; variantes: Table | null; alteracoes: Table | null
  totais: Record<string, number>; n_docs: number; ms: number
  por_mes: Table; por_filial: Table; por_cfop: Table; por_item: Table; por_status: Table; por_cst_pis: Table; por_nat: Table
}
interface RegSum { tipo: RawTipo; tipo_label: string; reg: string; descricao: string; n: number; entradas: number; saidas: number; arquivos: number }

const fmtRaiz = (r: string) => r.replace(/^(\d{2})(\d{3})(\d{3})$/, '$1.$2.$3')
const refKey = (r: FornRef) => r.cnpjs.join(',')

export function FornecedorPage() {
  const { state, set, options } = useApp()
  const fs = state.forn
  const upd = (p: Partial<FornState>) => set((s) => ({ forn: { ...s.forn, ...p } }))
  const pick = (ref: FornRef) => upd({ cnpjs: ref.cnpjs, nome: ref.nome, recentes: [ref, ...fs.recentes.filter((r) => refKey(r) !== refKey(ref))].slice(0, 8) })
  const comps = options?.competencias ?? []

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-auto p-3 tall:gap-3 tall:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <SearchBox onPick={pick} autoFocus={!fs.cnpjs.length} />
        <div className="flex h-[34px] items-center gap-1 rounded-lg border bg-panel pl-2 pr-0.5 text-[12.5px]">
          <CalendarRange className="h-4 w-4 text-muted" />
          <Select className="border-0" value={fs.comp_ini || ''} onChange={(e) => upd({ comp_ini: e.target.value || undefined })}>
            <option value="">Início</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
          </Select>
          <span className="text-muted">a</span>
          <Select className="border-0" value={fs.comp_fim || ''} onChange={(e) => upd({ comp_fim: e.target.value || undefined })}>
            <option value="">Fim</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
          </Select>
        </div>
        {fs.cnpjs.length > 0 && (
          <Tip content="Pasta de trabalho com cadastro, entradas consolidadas, notas, itens e as linhas dos arquivos (uma aba por registro)">
            <Button variant="primary" icon={<FileSpreadsheet className="h-4 w-4" />}
              onClick={() => runExport('/api/export/fornecedor', { cnpjs: fs.cnpjs, comp_ini: fs.comp_ini, comp_fim: fs.comp_fim }, 'Excel do fornecedor')}>
              Excel completo
            </Button>
          </Tip>
        )}
      </div>
      <IndexBanner />
      {fs.cnpjs.length === 0
        ? <Welcome recentes={fs.recentes} onPick={pick} onClear={() => upd({ recentes: [] })} />
        : <Profile fs={fs} upd={upd} />}
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------
function SearchBox({ onPick, autoFocus }: { onPick: (r: FornRef) => void; autoFocus?: boolean }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState<{ itens: Sug[]; raiz: { raiz: string; n: number; nome: string } | null } | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); return }
    setLoading(true)
    const t = setTimeout(() => {
      api.get(`/api/fornecedor/buscar?q=${encodeURIComponent(q.trim())}`).then((r) => { setRes(r); setHi(0) })
        .catch((e) => toast.error(e.message)).finally(() => setLoading(false))
    }, 220)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => {
    const out = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', out)
    return () => document.removeEventListener('mousedown', out)
  }, [])
  const digits = q.replace(/\D/g, '')
  const opts = useMemo(() => {
    const o: { key: string; title: string; sub: string; extra?: string; get: () => Promise<FornRef> }[] = []
    if (res?.raiz) {
      const r = res.raiz
      o.push({ key: 'raiz', title: `Todos os ${r.n} estabelecimentos da raiz ${fmtRaiz(r.raiz)}`, sub: r.nome || '',
        get: async () => ({ cnpjs: (await api.post('/api/fornecedor/raiz', { raiz: r.raiz })).cnpjs, nome: `${r.nome || ''} (raiz ${fmtRaiz(r.raiz)})` }) })
    }
    for (const s of res?.itens ?? []) {
      o.push({ key: s.cnpj_cpf, title: s.razao_social || fmtCnpj(s.cnpj_cpf), sub: `${fmtCnpj(s.cnpj_cpf)}${s.uf ? ` · ${s.uf}` : ''}`,
        extra: s.tem_entradas ? `${fmtBRL(s.vl_contabil)} em entradas` : 'somente cadastro / outras operações',
        get: async () => ({ cnpjs: [s.cnpj_cpf], nome: s.razao_social || fmtCnpj(s.cnpj_cpf) }) })
    }
    if ((digits.length === 14 || digits.length === 11) && /^[\d\s./-]+$/.test(q.trim()) && !o.some((x) => x.key === digits)) {
      o.push({ key: 'direto', title: `Procurar ${fmtCnpj(digits)} em todos os arquivos`, sub: 'Não consta no cadastro consolidado — a busca percorre as linhas dos TXT',
        get: async () => ({ cnpjs: [digits], nome: fmtCnpj(digits) }) })
    }
    return o
  }, [res, digits, q])
  const choose = async (i: number) => {
    const o = opts[i]
    if (!o) return
    try { onPick(await o.get()); setOpen(false); setQ('') } catch (e: any) { toast.error(e.message) }
  }
  return (
    <div ref={box} className="relative min-w-[280px] max-w-[640px] flex-1">
      <Input autoFocus={autoFocus} value={q} placeholder="CNPJ, CPF, raiz (8 dígitos) ou nome do fornecedor…" icon={<Search className="h-4 w-4" />}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(opts.length - 1, h + 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(0, h - 1)) }
          else if (e.key === 'Enter') { e.preventDefault(); choose(hi) }
          else if (e.key === 'Escape') setOpen(false)
        }} />
      {loading && <Loader2 className="absolute right-2.5 top-2.5 h-4 w-4 animate-spin text-muted" />}
      {open && q.trim().length >= 2 && (
        <div className="absolute left-0 right-0 top-[38px] z-50 max-h-[60vh] overflow-auto rounded-xl border bg-panel p-1 shadow-pop animate-in">
          {opts.length === 0 && !loading && <div className="px-3 py-4 text-center text-[12.5px] text-muted">Nenhum participante encontrado. Digite o CNPJ completo (14 dígitos) para procurar nas linhas dos arquivos.</div>}
          {opts.map((o, i) => (
            <button key={o.key} onMouseEnter={() => setHi(i)} onClick={() => choose(i)}
              className={cx('flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left', hi === i ? 'bg-accent/10' : 'hover:bg-sunken')}>
              <UserSearch className="h-4 w-4 shrink-0 text-muted" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium">{o.title}</div>
                <div className="truncate text-[12px] text-muted">{o.sub}</div>
              </div>
              {o.extra && <span className="shrink-0 text-[12px] text-muted">{o.extra}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Welcome({ recentes, onPick, onClear }: { recentes: FornRef[]; onPick: (r: FornRef) => void; onClear: () => void }) {
  return (
    <Card className="flex-1 overflow-auto">
      <div className="pt-6">
        <Empty icon={<UserSearch className="h-6 w-6" />} title="Busque um fornecedor pelo CNPJ, CPF, raiz ou nome">
          Mostra tudo o que existe sobre ele na base: cadastro em todos os arquivos (0150/0175), entradas consolidadas SPED Fiscal +
          EFD-Contribuições (sem duplicidade), notas fiscais, itens e cada linha dos TXT ligada a ele — entradas e saídas.
        </Empty>
      </div>
      {recentes.length > 0 && (
        <div className="mx-auto max-w-3xl px-6 pb-6">
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-muted"><History className="h-3.5 w-3.5" />Recentes
            <button className="ml-auto font-normal normal-case tracking-normal hover:text-fg" onClick={onClear}>limpar</button></div>
          <div className="flex flex-wrap gap-2">
            {recentes.map((r) => (
              <button key={refKey(r)} onClick={() => onPick(r)} className="rounded-lg border bg-panel px-3 py-1.5 text-left text-[12.5px] hover:bg-sunken">
                <div className="font-medium">{r.nome}</div>
                <div className="text-[11.5px] text-muted">{r.cnpjs.length > 1 ? `${r.cnpjs.length} CNPJs` : fmtCnpj(r.cnpjs[0])}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

// ------------------------------------------------------------------------------------------------------------
function Profile({ fs, upd }: { fs: FornState; upd: (p: Partial<FornState>) => void }) {
  const { dataVersion } = useApp()
  const body = useMemo(() => ({ cnpjs: fs.cnpjs, comp_ini: fs.comp_ini, comp_fim: fs.comp_fim }), [fs.cnpjs, fs.comp_ini, fs.comp_fim])
  const key = JSON.stringify(body) + dataVersion
  const [p, setP] = useState<Prof | null>(null)
  const [regs, setRegs] = useState<RegSum[] | null>(null)
  useEffect(() => {
    let alive = true
    setP(null); setRegs(null)
    api.post<Prof>('/api/fornecedor/perfil', body).then((r) => alive && setP(r)).catch((e) => toast.error(e.message))
    api.post('/api/fornecedor/arquivos', body).then((r) => alive && setRegs(r.registros)).catch((e) => toast.error(e.message))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const [kpiCollapsed, setKpiCollapsed] = useCollapsed('forn-kpis')
  const v = p?.variantes ? tableRows(p.variantes) : []
  const cur = v[0]
  const t = p?.totais
  const nLines = regs?.reduce((a, r) => a + r.n, 0)

  return (
    <>
      <Card className="shrink-0 px-4 py-3">
        <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 shrink-0 text-accent" />
              <h2 className="truncate text-[17px] font-semibold tracking-tight">{cur?.nome || fs.nome}</h2>
              <Button size="icon-sm" variant="ghost" aria-label="Limpar" onClick={() => upd({ cnpjs: [], nome: '' })}><X className="h-4 w-4" /></Button>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-muted">
              <span className="font-mono text-fg/85">{fs.cnpjs.length > 3 ? `${fs.cnpjs.length} CNPJs da raiz ${fmtRaiz(fs.cnpjs[0].slice(0, 8))}` : fs.cnpjs.map(fmtCnpj).join(' · ')}</span>
              {cur?.uf && <span>UF {cur.uf}</span>}
              {cur?.ie && <span>IE {cur.ie}</span>}
              {cur?.endereco && <span>{[cur.endereco, cur.numero, cur.bairro].filter(Boolean).join(', ')}</span>}
              {v.length > 1 && <Badge tone="warn">{v.length} versões de cadastro</Badge>}
              {p && !p.cadastro && <Badge tone="warn">Sem registro 0150 nos arquivos do período</Badge>}
            </div>
          </div>
          <div className="flex items-center gap-2 text-[12px] text-muted">
            {p ? <span>{p.ms} ms</span> : <Spinner />}
            <CollapseToggle collapsed={kpiCollapsed} onToggle={() => setKpiCollapsed(!kpiCollapsed)} label="indicadores" />
          </div>
        </div>
        {!kpiCollapsed && (
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 2xl:grid-cols-8">
            <Kpi label="Valor contábil" icon={<Receipt className="h-3.5 w-3.5" />} loading={!p} value={fmtBRL(t?.vl_contabil)} hint={p ? `${fmtInt(p.n_docs)} documentos de entrada` : undefined} />
            <Kpi label="ICMS" icon={<Landmark className="h-3.5 w-3.5" />} loading={!p} value={fmtBRL(t?.vl_icms)} />
            <Kpi label="ICMS-ST + FCP" icon={<Landmark className="h-3.5 w-3.5" />} loading={!p} value={fmtBRL(t?.vl_icms_st_fcp)} />
            <Kpi label="IPI" icon={<Coins className="h-3.5 w-3.5" />} loading={!p} value={fmtBRL(t?.vl_ipi)} />
            <Kpi label="PIS" icon={<BadgePercent className="h-3.5 w-3.5" />} loading={!p} value={fmtBRL(t?.vl_pis)} />
            <Kpi label="COFINS" icon={<BadgePercent className="h-3.5 w-3.5" />} loading={!p} value={fmtBRL(t?.vl_cofins)} />
            <Kpi label="Recuperáveis" tone="text-ok" loading={!p} value={fmtBRL(t?.vl_trib_recuperaveis)} />
            <Kpi label="Linhas nos TXT" icon={<FileText className="h-3.5 w-3.5" />} loading={!regs} value={fmtInt(nLines)} hint={regs ? `${new Set(regs.map((r) => r.reg)).size} registros, entradas e saídas` : undefined} />
          </div>
        )}
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={fs.tab as any} onChange={(tab) => upd({ tab })} options={[
          { value: 'geral', label: 'Visão geral' }, { value: 'notas', label: 'Notas fiscais' }, { value: 'itens', label: 'Itens' },
          { value: 'arquivos', label: `Nos arquivos${nLines != null ? ` (${fmtInt(nLines)})` : ''}` }, { value: 'cadastro', label: 'Cadastro' },
        ]} />
        <span className="text-[12px] text-muted">
          {fs.tab === 'arquivos' ? 'Linhas dos TXT como estão — entradas e saídas, sem cruzamento'
            : fs.tab === 'cadastro' ? 'Registros 0150 e 0175 de todos os arquivos'
              : 'Entradas consolidadas SPED Fiscal + EFD-Contribuições, sem duplicidade'}
        </span>
      </div>

      <div className="flex min-h-[380px] flex-1 flex-col">
        {fs.tab === 'geral' && <Overview p={p} />}
        {fs.tab === 'notas' && (
          <DocsPanel path={[]} base={{ gf: { fornecedores: fs.cnpjs, comp_ini: fs.comp_ini, comp_fim: fs.comp_fim }, rules: null }}
            ctx={{ gf: { fornecedores: fs.cnpjs, comp_ini: fs.comp_ini, comp_fim: fs.comp_fim }, rules: null }}
            onClose={() => upd({ tab: 'geral' })} onExport={(u, b, l) => runExport(u, b, l)} />
        )}
        {fs.tab === 'itens' && <ItemsTab p={p} />}
        {fs.tab === 'arquivos' && <FilesTab regs={regs} body={body} />}
        {fs.tab === 'cadastro' && <CadastroTab p={p} />}
      </div>
    </>
  )
}

function useCols(t: Table | null | undefined, keys: string[], labels: Record<string, string> = {}): MiniCol[] {
  const { metricLabel, dimLabel } = useApp()
  return keys.filter((k) => !t || t.columns.includes(k)).map((k) => ({ key: k, label: labels[k] ?? (metricLabel(k) !== k ? metricLabel(k) : dimLabel(k)), type: typeOf(t, k) }))
}

const VALS = ['vl_contabil', 'vl_icms', 'vl_ipi', 'vl_pis', 'vl_cofins', 'vl_trib_recuperaveis']

function Overview({ p }: { p: Prof | null }) {
  const mes = useCols(p?.por_mes, ['competencia', ...VALS])
  mes[0] = { ...mes[0], render: (r) => fmtComp(r.competencia) }
  const fil = useCols(p?.por_filial, ['filial', ...VALS])
  if (fil[0]) fil[0] = { ...fil[0], render: (r) => <DimCell dim="filial" code={r.filial} desc={r.filial__desc} /> }
  const cfop = useCols(p?.por_cfop, ['cfop', ...VALS])
  const st = useCols(p?.por_status, ['status_efd', 'vl_contabil', 'vl_pis', 'vl_cofins'])
  const cst = useCols(p?.por_cst_pis, ['cst_pis', 'vl_contabil', 'vl_pis', 'vl_cofins'])
  const nat = useCols(p?.por_nat, ['nat_bc_cred', 'vl_contabil', 'vl_pis', 'vl_cofins'])
  if (!p) return <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-[220px] rounded-xl" />)}</div>
  const rowsMes = tableRows(p.por_mes)
  const max = Math.max(1, ...rowsMes.map((r) => Number(r.vl_contabil) || 0))
  return (
    <div className="grid grid-cols-1 gap-3 pb-2 xl:grid-cols-2">
      <Card className="xl:col-span-2">
        <div className="flex items-center justify-between border-b px-4 py-2"><span className="text-[13px] font-semibold">Entradas por competência</span><span className="text-[12px] text-muted">{rowsMes.length} mês(es)</span></div>
        <div className="flex h-[90px] items-end gap-1 px-4 pt-2">
          {rowsMes.map((r) => (
            <Tip key={r.competencia} content={`${fmtComp(r.competencia)}: ${fmtBRL(r.vl_contabil)}`}>
              <div className="flex h-full max-w-[48px] flex-1 flex-col justify-end"><div className="rounded-t bg-accent/50 hover:bg-accent/80" style={{ height: `${Math.max(2, (Number(r.vl_contabil) / max) * 100)}%` }} /></div>
            </Tip>
          ))}
        </div>
        <MiniTable cols={mes} rows={rowsMes} total maxH={260} />
      </Card>
      <Card><div className="border-b px-4 py-2 text-[13px] font-semibold">Por unidade (filial)</div><MiniTable cols={fil} rows={tableRows(p.por_filial)} total /></Card>
      <Card><div className="border-b px-4 py-2 text-[13px] font-semibold">Por CFOP</div><MiniTable cols={cfop} rows={tableRows(p.por_cfop)} total /></Card>
      <Card><div className="border-b px-4 py-2 text-[13px] font-semibold">Situação na EFD-Contribuições</div><MiniTable cols={st} rows={tableRows(p.por_status)} total /></Card>
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2">
          <div><div className="border-b px-4 py-2 text-[13px] font-semibold">CST PIS</div><MiniTable cols={cst} rows={tableRows(p.por_cst_pis)} /></div>
          <div className="md:border-l"><div className="border-b px-4 py-2 text-[13px] font-semibold">Natureza da base de crédito</div><MiniTable cols={nat} rows={tableRows(p.por_nat)} /></div>
        </div>
      </Card>
    </div>
  )
}

function ItemsTab({ p }: { p: Prof | null }) {
  const { metricLabel, dimLabel } = useApp()
  const mx = useMaximize()
  const [sort, toggleSort] = useSort({ key: 'vl_contabil', dir: 'desc' })
  const g = useMemo(() => {
    const x = tableToGrid(p?.por_item ?? null, { sticky: 1 })
    x.columns = x.columns.filter((c) => c.key !== 'item__desc').map((c) => ({
      ...c, label: c.key === 'item' ? dimLabel('item') : metricLabel(c.key),
      width: c.key === 'item' ? 360 : c.width,
      render: c.key === 'item' ? (r: any) => <DimCell dim="item" code={r.cells.item} desc={r.cells.item__desc} /> : undefined,
    }))
    return x
  }, [p, metricLabel, dimLabel])
  const totals = useMemo(() => p?.totais ?? null, [p])
  return (
    <>
      <MaxBackdrop on={mx.on} onClose={mx.toggle} />
      <Card className={cx('flex min-h-0 flex-1 flex-col', mx.cls)}>
        <div className="flex items-center gap-2 border-b px-4 py-2">
          <span className="text-[13px] font-semibold">Itens comprados</span>
          <span className="text-[12px] text-muted">{p ? `${fmtInt(p.por_item.rows.length)} item(ns)` : ''}</span>
          <div className="flex-1" /><MaxButton on={mx.on} onClick={mx.toggle} size="icon-sm" />
        </div>
        <div className="min-h-0 flex-1 p-2">
          <DataGrid columns={g.columns} rows={sortRows(g.rows, sort)} totals={totals} loading={!p} dense sort={sort} onSort={toggleSort} />
        </div>
      </Card>
    </>
  )
}

function FilesTab({ regs, body }: { regs: RegSum[] | null; body: any }) {
  const [sel, setSel] = useState<{ tipo: RawTipo; reg: string } | null>(null)
  const [oper, setOper] = useState<'' | '0' | '1'>('')
  useEffect(() => {
    if (regs && regs.length && (!sel || !regs.some((r) => r.tipo === sel.tipo && r.reg === sel.reg))) {
      const first = regs.find((r) => /^[CDA]1/.test(r.reg)) ?? regs[0]
      setSel({ tipo: first.tipo, reg: first.reg })
    }
  }, [regs]) // eslint-disable-line react-hooks/exhaustive-deps
  const groups = useMemo(() => {
    const m = new Map<string, RegSum[]>()
    for (const r of regs ?? []) { if (!m.has(r.tipo_label)) m.set(r.tipo_label, []); m.get(r.tipo_label)!.push(r) }
    return [...m.entries()]
  }, [regs])
  const info = regs?.find((r) => sel && r.tipo === sel.tipo && r.reg === sel.reg)
  return (
    <div className="flex min-h-0 flex-1 gap-3">
      <SidePanel id="forn-regs" title="Registros" defaultWidth={300}>
        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="border-b px-3 py-2 text-[12px] text-muted">Linhas ligadas ao participante, por registro</div>
          <div className="min-h-0 flex-1 overflow-auto p-1.5">
            {!regs && <div className="space-y-2 p-2">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton h-8" />)}</div>}
            {regs && regs.length === 0 && <div className="p-4 text-center text-[12.5px] text-muted">Nenhuma linha nos arquivos do período</div>}
            {groups.map(([label, list]) => (
              <div key={label} className="mb-2">
                <div className="sticky top-0 z-[1] bg-panel/95 px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted backdrop-blur">{label}</div>
                {list.map((r) => {
                  const on = sel?.tipo === r.tipo && sel?.reg === r.reg
                  return (
                    <button key={r.tipo + r.reg} onClick={() => setSel({ tipo: r.tipo, reg: r.reg })}
                      className={cx('flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left', on ? 'bg-accent/10' : 'hover:bg-sunken')}>
                      <span className={cx('mt-px w-[42px] shrink-0 font-mono text-[12.5px] font-semibold', on ? 'text-accent' : '')}>{r.reg}</span>
                      <span className="min-w-0 flex-1 text-[12px] leading-snug text-muted">{r.descricao}
                        {(r.entradas > 0 || r.saidas > 0) && <span className="block text-[11px]">{fmtInt(r.entradas)} entrada(s) · {fmtInt(r.saidas)} saída(s)</span>}
                      </span>
                      <span className="num shrink-0 text-[11.5px] text-muted">{fmtInt(r.n)}</span>
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
        </Card>
      </SidePanel>
      <div className="flex min-w-0 flex-1 flex-col">
        {sel ? <RegGrid tipo={sel.tipo} reg={sel.reg} descr={info?.descricao ?? ''} body={body} oper={oper} setOper={setOper} hasOper={!!info && (info.entradas > 0 || info.saidas > 0)} />
          : <Card className="flex-1"><Empty icon={<FileText className="h-6 w-6" />} title="Escolha um registro à esquerda" /></Card>}
      </div>
    </div>
  )
}

function RegGrid({ tipo, reg, descr, body, oper, setOper, hasOper }: { tipo: RawTipo; reg: string; descr: string; body: any; oper: '' | '0' | '1'; setOper: (o: '' | '0' | '1') => void; hasOper: boolean }) {
  const q = { reg, participantes: body.cnpjs, comp_ini: body.comp_ini, comp_fim: body.comp_fim, operacao: hasOper ? oper : '' }
  const key = `${tipo}|${JSON.stringify(q)}`
  const { data, loading, loadMore } = useInfinite(`/api/raw/${tipo}/query`, q, key)
  const g = useMemo(() => toGrid(data), [data])
  const mx = useMaximize()
  return (
    <>
      <MaxBackdrop on={mx.on} onClose={mx.toggle} />
      <Card className={cx('flex min-h-0 flex-1 flex-col', mx.cls)}>
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2"><span className="font-mono text-[15px] font-semibold">{reg}</span>
              <span className="truncate text-[13px] text-muted">{tipo === 'ICMS_IPI' ? 'SPED Fiscal' : 'EFD-Contribuições'} · {descr}</span></div>
            <div className="text-[12px] text-muted">{data?.total != null ? `${fmtInt(data.total)} linha(s)` : loading ? 'Consultando…' : ''}{data?.ms != null && <span className="opacity-60"> · {data.ms} ms</span>}</div>
          </div>
          {hasOper && <Segmented value={oper || 'todas'} onChange={(v) => setOper(v === 'todas' ? '' : (v as any))}
            options={[{ value: 'todas', label: 'Todas' }, { value: '0', label: 'Entradas' }, { value: '1', label: 'Saídas' }]} />}
          <Button icon={<ArrowDownToLine className="h-4 w-4" />} disabled={!data?.total} onClick={() => exportTo(tipo, q, 'xlsx', reg)}>Excel</Button>
          <MaxButton on={mx.on} onClick={mx.toggle} />
        </div>
        <div className="min-h-0 flex-1 p-2">
          <DataGrid columns={g.columns} rows={g.rows} loading={loading} dense rowHeight={32} onEndReached={loadMore} emptyText={loading ? '' : 'Nenhuma linha'} />
        </div>
      </Card>
    </>
  )
}

function CadastroTab({ p }: { p: Prof | null }) {
  const LBL: Record<string, string> = {
    nome: 'Nome', cnpj: 'CNPJ', cpf: 'CPF', ie: 'IE', uf: 'UF', cod_mun: 'Município (IBGE)', endereco: 'Endereço', numero: 'Número',
    bairro: 'Bairro', primeira: 'Primeira competência', ultima: 'Última competência', arquivos: 'Arquivos', codigos: 'Códigos (COD_PART)',
    unidades: 'Unidades', ocorrencias: 'Ocorrências', arquivo_tipo: 'Arquivo', competencia: 'Competência', unidade: 'Unidade (CNPJ)',
    cod_part: 'COD_PART', cod_pais: 'País', complemento: 'Complemento', file_id: 'Arquivo (ID)', line_no: 'Linha',
    dt_alt: 'Data da alteração', nr_campo: 'Campo alterado', cont_ant: 'Conteúdo anterior',
  }
  const v = useCols(p?.variantes, ['nome', 'cnpj', 'cpf', 'ie', 'uf', 'cod_mun', 'endereco', 'numero', 'bairro', 'primeira', 'ultima', 'arquivos', 'codigos', 'unidades', 'ocorrencias'], LBL)
  v.forEach((c) => { if (c.key === 'primeira' || c.key === 'ultima') c.render = (r) => fmtComp(r[c.key]) })
  const all = useCols(p?.cadastro, ['arquivo_tipo', 'competencia', 'unidade', 'cod_part', 'nome', 'cnpj', 'cpf', 'ie', 'uf', 'cod_mun', 'endereco', 'numero', 'complemento', 'bairro', 'file_id', 'line_no'], LBL)
  const alt = useCols(p?.alteracoes, ['arquivo_tipo', 'competencia', 'dt_alt', 'nr_campo', 'cont_ant', 'file_id', 'line_no'], LBL)
  if (!p) return <div className="skeleton h-[300px] rounded-xl" />
  return (
    <div className="flex flex-col gap-3 pb-2">
      <Card><div className="border-b px-4 py-2 text-[13px] font-semibold">Versões do cadastro</div><MiniTable cols={v} rows={tableRows(p.variantes)} empty="Nenhum 0150 com este CNPJ/CPF no período" /></Card>
      {p.alteracoes && <Card><div className="border-b px-4 py-2 text-[13px] font-semibold">Alterações (0175)</div><MiniTable cols={alt} rows={tableRows(p.alteracoes)} /></Card>}
      <Card><div className="border-b px-4 py-2 text-[13px] font-semibold">Todos os registros 0150</div><MiniTable cols={all} rows={tableRows(p.cadastro)} maxH={420} /></Card>
    </div>
  )
}
