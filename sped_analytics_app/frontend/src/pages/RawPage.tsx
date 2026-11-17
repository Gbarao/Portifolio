import { ArrowDownToLine, Building2, CalendarRange, FileSpreadsheet, FileText, FileX, Filter, ListOrdered, Plus, RefreshCw, Search, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { DataGrid, type GridCol, type GridRow } from '../components/DataGrid'
import { FilterButton, MultiList } from '../components/FilterBar'
import { Badge, Button, Card, Empty, Input, Menu, MenuItem, Popover, Segmented, Select, Spinner, Tip, cx } from '../components/ui'
import { api, download, waitJob } from '../lib/api'
import { fmtCnpj, fmtComp, fmtInt } from '../lib/format'
import { EMPTY_RAW, useApp } from '../lib/store'
import type { ColType, RawCond, RawState, RawTipo } from '../lib/types'

interface Overview {
  arquivos: { id_arquivo: number; competencia: string; cnpj: string; nome: string; finalidade: string; linhas: number; caminho_origem: string; indexado: boolean }[]
  unidades: { cnpj: string; nome: string | null; linhas: number }[]
  competencias: string[]
  blocos: Record<string, string>
  operadores: Record<string, string>
}
interface RegInfo { reg: string; n: number; bloco: string; descricao: string; conhecido: boolean }
interface Page { columns: string[]; types: ColType[]; rows: any[][]; total: number | null; labels?: Record<string, string>; fields?: string[]; docReg?: string | null; ms?: number }

const PAGE = 1000
const WIDTHS: Record<string, number> = {
  competencia: 108, unidade: 160, arquivo: 92, linha_no: 92, doc_num_doc: 120, doc_reg: 92, part_cnpj_cpf: 160, part_nome: 240, item_descr: 240,
  item_ncm: 100, item_tipo: 86, linha_original: 640, reg: 70,
}

export function RawPage({ tipo }: { tipo: RawTipo }) {
  const { state, set, dataVersion } = useApp()
  const rs: RawState = state.raw?.[tipo] ?? EMPTY_RAW
  const upd = useCallback((patch: Partial<RawState>) => set((s) => ({ raw: { ...s.raw, [tipo]: { ...s.raw[tipo], ...patch } } })), [set, tipo])
  const label = tipo === 'ICMS_IPI' ? 'SPED Fiscal' : 'EFD-Contribuições'

  // ---------------------------------------------------------------- visão geral e registros
  const [ov, setOv] = useState<Overview | null>(null)
  const [regs, setRegs] = useState<RegInfo[] | null>(null)
  const loadOverview = useCallback(() => api.get<Overview>(`/api/raw/${tipo}/overview`).then(setOv).catch((e) => toast.error(e.message)), [tipo])
  useEffect(() => { loadOverview() }, [loadOverview, dataVersion])
  const scope = { competencias: rs.competencias, comp_ini: rs.comp_ini, comp_fim: rs.comp_fim, unidades: rs.unidades, arquivos: rs.arquivos }
  const scopeKey = JSON.stringify(scope)
  useEffect(() => {
    setRegs(null)
    api.post<RegInfo[]>(`/api/raw/${tipo}/registers`, scope).then(setRegs).catch((e) => toast.error(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo, scopeKey, dataVersion])

  const pending = ov?.arquivos.filter((a) => !a.indexado) ?? []
  const [indexing, setIndexing] = useState<string | null>(null)
  const runIndex = async () => {
    setIndexing('Iniciando…')
    try {
      const { job } = await api.post('/api/raw/index')
      const j = await waitJob(job, (x) => setIndexing(`${x.msg} · ${Math.round(x.frac * 100)}%`))
      if (j.status === 'error') toast.error(j.error || 'Falha')
      else {
        const r = j.result
        toast.success(`${r.indexados} arquivo(s) indexado(s)`, {
          description: r.nao_encontrados.length || r.alterados.length
            ? `${r.nao_encontrados.length} não encontrado(s) no caminho original e ${r.alterados.length} alterado(s) desde a importação — reimporte esses arquivos.` : undefined,
          duration: 10000,
        })
      }
      await loadOverview()
      setRegs(await api.post(`/api/raw/${tipo}/registers`, scope))
    } catch (e: any) { toast.error(e.message) } finally { setIndexing(null) }
  }

  // ---------------------------------------------------------------- filtros (barra superior)
  const unitOpts = useMemo(() => (ov?.unidades ?? []).map((u) => [u.cnpj, u.nome || u.cnpj] as [string, string]), [ov])
  const fileOpts = useMemo(() => (ov?.arquivos ?? []).map((a) => [String(a.id_arquivo), `${fmtComp(a.competencia)} · ${fmtCnpj(a.cnpj)} · ${a.nome}${a.finalidade === 'RETIFICADORA' ? ' (retificadora)' : ''}`] as [string, string]), [ov])
  const comps = ov?.competencias ?? []
  const periodo = rs.competencias.length ? `${rs.competencias.length} mês(es)` : rs.comp_ini || rs.comp_fim ? `${rs.comp_ini ? fmtComp(rs.comp_ini) : '…'} – ${rs.comp_fim ? fmtComp(rs.comp_fim) : '…'}` : undefined
  const [busca, setBusca] = useState(rs.busca)
  useEffect(() => { setBusca(rs.busca) }, [rs.busca])
  useEffect(() => { const t = setTimeout(() => { if (busca !== rs.busca) upd({ busca }) }, 450); return () => clearTimeout(t) }, [busca]) // eslint-disable-line react-hooks/exhaustive-deps
  const anyFilter = rs.competencias.length || rs.comp_ini || rs.comp_fim || rs.unidades.length || rs.arquivos.length || rs.operacao || rs.busca || rs.condicoes.length

  const filterBar = (
    <div className="flex flex-wrap items-center gap-2">
      <FilterButton icon={<CalendarRange className="h-4 w-4" />} label="Período" count={periodo ? 1 : 0} summary={periodo}>
        <div className="w-[340px] space-y-3 p-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1 text-[12px] text-muted">De
              <Select className="w-full" value={rs.comp_ini || ''} onChange={(e) => upd({ comp_ini: e.target.value || undefined, competencias: [] })}>
                <option value="">Início</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
              </Select>
            </label>
            <label className="space-y-1 text-[12px] text-muted">Até
              <Select className="w-full" value={rs.comp_fim || ''} onChange={(e) => upd({ comp_fim: e.target.value || undefined, competencias: [] })}>
                <option value="">Fim</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
              </Select>
            </label>
          </div>
          <div className="flex max-h-[180px] flex-wrap gap-1 overflow-auto">
            {comps.map((c) => {
              const on = rs.competencias.includes(c)
              return <button key={c} onClick={() => upd({ competencias: on ? rs.competencias.filter((x) => x !== c) : [...rs.competencias, c], comp_ini: undefined, comp_fim: undefined })}
                className={cx('rounded-md border px-2 py-1 text-[12px]', on ? 'border-accent bg-accent text-accent-fg' : 'hover:bg-sunken')}>{fmtComp(c)}</button>
            })}
          </div>
        </div>
      </FilterButton>
      <FilterButton icon={<Building2 className="h-4 w-4" />} label="Unidade" count={rs.unidades.length}
        summary={rs.unidades.length === 1 ? (unitOpts.find((u) => u[0] === rs.unidades[0])?.[1] ?? fmtCnpj(rs.unidades[0])) : rs.unidades.length ? `${rs.unidades.length} selecionadas` : undefined}>
        <MultiList options={unitOpts} value={rs.unidades} onChange={(v) => upd({ unidades: v })} format={fmtCnpj} />
      </FilterButton>
      <FilterButton icon={<FileText className="h-4 w-4" />} label="Arquivo" count={rs.arquivos.length} summary={rs.arquivos.length ? `${rs.arquivos.length} arquivo(s)` : undefined}>
        <MultiList options={fileOpts} value={rs.arquivos.map(String)} onChange={(v) => upd({ arquivos: v.map(Number) })} />
      </FilterButton>
      {rs.modo === 'registro' && (
        <Tip content="Vale para documentos com IND_OPER (C100, D100, C500, A100...) e para os registros filhos deles (C170, C190...)">
          <div><Segmented value={rs.operacao || 'todas'} onChange={(v) => upd({ operacao: v === 'todas' ? '' : (v as any) })}
            options={[{ value: 'todas', label: 'Todas' }, { value: '0', label: 'Entradas' }, { value: '1', label: 'Saídas' }]} /></div>
        </Tip>
      )}
      <Input className="w-[260px]" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Texto em qualquer campo da linha…" icon={<Search className="h-4 w-4" />} />
      {anyFilter ? <Button variant="ghost" size="sm" className="text-muted" icon={<X className="h-4 w-4" />}
        onClick={() => { upd({ competencias: [], comp_ini: undefined, comp_fim: undefined, unidades: [], arquivos: [], operacao: '', busca: '', condicoes: [] }); setBusca('') }}>Limpar filtros</Button> : null}
    </div>
  )

  if (ov && ov.arquivos.length === 0) {
    return (
      <div className="p-5">
        <Card><Empty icon={<FileX className="h-6 w-6" />} title={`Nenhum arquivo do ${label} importado`}>
          Importe os arquivos na tela <button className="font-medium text-accent underline" onClick={() => set({ page: 'arquivos' })}>Arquivos</button>.
        </Empty></Card>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-5">
      {filterBar}
      {pending.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12.5px]">
          <RefreshCw className="h-4 w-4 shrink-0 text-warn" />
          <span className="flex-1">{pending.length} arquivo(s) foram importados antes desta tela existir e ainda não têm as linhas originais guardadas.
            O programa pode lê-los de novo no caminho de origem, se ainda estiverem lá e sem alteração.</span>
          {indexing ? <span className="flex items-center gap-2 text-muted"><Spinner />{indexing}</span>
            : <Button size="sm" variant="primary" onClick={runIndex}>Indexar agora</Button>}
        </div>
      )}
      <div className="flex min-h-0 flex-1 gap-3">
        <RegisterList regs={regs} blocos={ov?.blocos ?? {}} rs={rs} upd={upd} />
        <div className="flex min-w-0 flex-1 flex-col">
          {rs.modo === 'registro'
            ? <RegisterView tipo={tipo} rs={rs} upd={upd} regs={regs} ops={ov?.operadores ?? {}} />
            : <FileView tipo={tipo} rs={rs} upd={upd} files={ov?.arquivos ?? []} />}
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------
function RegisterList({ regs, blocos, rs, upd }: { regs: RegInfo[] | null; blocos: Record<string, string>; rs: RawState; upd: (p: Partial<RawState>) => void }) {
  const [q, setQ] = useState('')
  const groups = useMemo(() => {
    const n = q.trim().toLowerCase()
    const list = (regs ?? []).filter((r) => !n || r.reg.toLowerCase().includes(n) || r.descricao.toLowerCase().includes(n))
    const m = new Map<string, RegInfo[]>()
    list.forEach((r) => { if (!m.has(r.bloco)) m.set(r.bloco, []); m.get(r.bloco)!.push(r) })
    return [...m.entries()]
  }, [regs, q])
  return (
    <Card className="flex w-[300px] shrink-0 flex-col overflow-hidden">
      <div className="space-y-2 border-b p-2.5">
        <Segmented value={rs.modo} onChange={(m) => upd({ modo: m })} options={[
          { value: 'registro', label: 'Por registro', icon: <ListOrdered className="h-4 w-4" /> },
          { value: 'arquivo', label: 'Arquivo', icon: <FileText className="h-4 w-4" /> },
        ]} />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar registro (C170, apuração…)" icon={<Search className="h-4 w-4" />} />
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-1.5">
        {!regs && <div className="space-y-2 p-2">{Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton h-8" />)}</div>}
        {regs && regs.length === 0 && <div className="p-4 text-center text-[12.5px] text-muted">Nenhuma linha para os filtros</div>}
        {groups.map(([b, list]) => (
          <div key={b} className="mb-1.5">
            <div className="sticky top-0 z-[1] bg-panel/95 px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted backdrop-blur">
              Bloco {b}{blocos[b] ? <span className="font-normal normal-case tracking-normal"> · {blocos[b]}</span> : null}
            </div>
            {list.map((r) => {
              const on = rs.modo === 'registro' && rs.reg === r.reg
              const pick = () => rs.modo === 'registro'
                ? upd({ reg: r.reg, condicoes: [] })
                : upd({ registrosArquivo: rs.registrosArquivo.split(/[,;\s]+/).filter(Boolean).includes(r.reg) ? rs.registrosArquivo : [...rs.registrosArquivo.split(/[,;\s]+/).filter(Boolean), r.reg].join(', ') })
              return (
                <button key={r.reg} onClick={pick}
                  className={cx('flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors', on ? 'bg-accent/10' : 'hover:bg-sunken')}>
                  <span className={cx('mt-px w-[42px] shrink-0 font-mono text-[12.5px] font-semibold', on ? 'text-accent' : 'text-fg/90')}>{r.reg}</span>
                  <span className="min-w-0 flex-1 text-[12px] leading-snug text-muted">{r.descricao || <i>sem descrição no catálogo</i>}</span>
                  <span className="num shrink-0 text-[11.5px] text-muted">{fmtInt(r.n)}</span>
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </Card>
  )
}

// ------------------------------------------------------------------------------------------------------------
function useInfinite(url: string, body: any, key: string) {
  const [data, setData] = useState<Page | null>(null)
  const [loading, setLoading] = useState(false)
  const gen = useRef(0)
  const more = useRef(false)
  useEffect(() => {
    const g = ++gen.current
    setLoading(true); setData(null)
    api.post<Page>(url, { ...body, offset: 0, limit: PAGE })
      .then((r) => { if (g === gen.current) setData(r) })
      .catch((e) => { if (g === gen.current) { toast.error(e.message); setData({ columns: [], types: [], rows: [], total: 0 }) } })
      .finally(() => { if (g === gen.current) setLoading(false) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const loadMore = useCallback(() => {
    if (!data || more.current || data.total == null || data.rows.length >= data.total) return
    more.current = true
    const g = gen.current
    api.post<Page>(url, { ...body, offset: data.rows.length, limit: PAGE })
      .then((r) => { if (g === gen.current) setData((d) => d ? { ...d, rows: [...d.rows, ...r.rows] } : d) })
      .catch((e) => toast.error(e.message))
      .finally(() => { more.current = false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, key])
  return { data, loading, loadMore }
}

function toGrid(p: Page | null): { columns: GridCol[]; rows: GridRow[] } {
  if (!p) return { columns: [], rows: [] }
  const columns: GridCol[] = p.columns.map((c, i) => ({
    key: c, label: p.labels?.[c] ?? c, type: p.types[i] ?? 'text',
    width: WIDTHS[c] ?? (/^(CHV_|doc_chv_)/i.test(c) ? 340 : /DESCR|TXT|NOME|END$|COMPL/i.test(c) ? 240 : undefined),
    sticky: c === 'linha_no',
    render: c === 'linha_original' ? (r: GridRow) => <span className="font-mono text-[11.5px] text-muted">{r.cells.linha_original}</span> : undefined,
  }))
  const rows = p.rows.map((r, i) => ({ id: String(i), cells: Object.fromEntries(p.columns.map((c, j) => [c, r[j]])) }))
  return { columns, rows }
}

function exportTo(tipo: RawTipo, body: any, fmt: 'xlsx' | 'csv', what: string) {
  const id = toast.loading(`Gerando ${fmt === 'xlsx' ? 'Excel' : 'CSV'} de ${what}…`)
  api.post(`/api/raw/${tipo}/export`, { ...body, fmt })
    .then((r) => {
      toast.success(`${fmt === 'xlsx' ? 'Excel' : 'CSV'} pronto${r.linhas != null ? ` — ${fmtInt(r.linhas)} linhas` : ''}`, {
        id, description: r.path, duration: 9000, action: { label: 'Abrir pasta', onClick: () => api.post('/api/open-folder', { path: r.path }) },
      })
      download(r.url)
    })
    .catch((e) => toast.error(e.message, { id }))
}

function RegisterView({ tipo, rs, upd, regs, ops }: { tipo: RawTipo; rs: RawState; upd: (p: Partial<RawState>) => void; regs: RegInfo[] | null; ops: Record<string, string> }) {
  const body = { reg: rs.reg, competencias: rs.competencias, comp_ini: rs.comp_ini, comp_fim: rs.comp_fim, unidades: rs.unidades,
    arquivos: rs.arquivos, operacao: rs.operacao, busca: rs.busca, condicoes: rs.condicoes }
  const key = `${tipo}|${JSON.stringify(body)}`
  const { data, loading, loadMore } = useInfinite(`/api/raw/${tipo}/query`, body, key)
  const g = useMemo(() => toGrid(data), [data])
  const info = regs?.find((r) => r.reg === rs.reg)
  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[15px] font-semibold">{rs.reg}</span>
            <span className="truncate text-[13px] text-muted">{info?.descricao}</span>
          </div>
          <div className="text-[12px] text-muted">
            {data?.total != null ? <>{fmtInt(data.total)} linha(s){data.rows.length < data.total ? ` · ${fmtInt(data.rows.length)} carregadas (role para carregar mais)` : ''}</> : loading ? 'Consultando…' : ''}
            {data?.docReg && <> · contexto do documento-pai <b className="font-mono">{data.docReg}</b></>}
            {data?.ms != null && <span className="opacity-60"> · {data.ms} ms</span>}
          </div>
        </div>
        <Conditions fields={data?.fields ?? []} ops={ops} value={rs.condicoes} onChange={(c) => upd({ condicoes: c })} />
        <Menu trigger={<Button variant="primary" icon={<ArrowDownToLine className="h-4 w-4" />} disabled={!data?.total}>Exportar</Button>}>
          <MenuItem icon={<FileSpreadsheet className="h-4 w-4" />} hint="Todas as linhas filtradas, com os nomes oficiais dos campos" onSelect={() => exportTo(tipo, body, 'xlsx', rs.reg)}>Excel (.xlsx)</MenuItem>
          <MenuItem icon={<FileText className="h-4 w-4" />} hint="Separador ; e vírgula decimal" onSelect={() => exportTo(tipo, body, 'csv', rs.reg)}>CSV</MenuItem>
        </Menu>
      </div>
      {rs.condicoes.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b px-4 py-2">
          {rs.condicoes.map((c, i) => (
            <Badge key={i} tone="accent" className="py-1">
              <span className="font-mono">{c.campo}</span> {ops[c.op] ?? c.op} {!['vazio', 'preenchido'].includes(c.op) && <b>{c.valor}</b>}
              <button className="ml-1 opacity-70 hover:opacity-100" onClick={() => upd({ condicoes: rs.condicoes.filter((_, j) => j !== i) })}><X className="h-3 w-3" /></button>
            </Badge>
          ))}
        </div>
      )}
      <div className="min-h-0 flex-1 p-2">
        <DataGrid columns={g.columns} rows={g.rows} loading={loading} dense rowHeight={32} onEndReached={loadMore}
          emptyText={loading ? '' : 'Nenhuma linha deste registro para os filtros'} />
      </div>
    </Card>
  )
}

function Conditions({ fields, ops, value, onChange }: { fields: string[]; ops: Record<string, string>; value: RawCond[]; onChange: (c: RawCond[]) => void }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<RawCond[]>(value)
  useEffect(() => { if (open) setDraft(value.length ? value : [{ campo: fields[0] ?? '', op: '=', valor: '' }]) }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  const set = (i: number, p: Partial<RawCond>) => setDraft((d) => d.map((c, j) => (j === i ? { ...c, ...p } : c)))
  return (
    <Popover open={open} onOpenChange={setOpen} align="end" trigger={
      <Button icon={<Filter className="h-4 w-4" />}>Condições {value.length ? <Badge tone="accent">{value.length}</Badge> : null}</Button>
    }>
      <div className="w-[560px] space-y-2 p-3">
        <div className="text-[12px] text-muted">Filtre por qualquer campo do registro (todas as condições precisam ser atendidas).</div>
        {draft.map((c, i) => (
          <div key={i} className="flex items-center gap-2">
            <Select className="w-[190px]" value={c.campo} onChange={(e) => set(i, { campo: e.target.value })}>
              {fields.map((f) => <option key={f} value={f}>{f}</option>)}
            </Select>
            <Select className="w-[150px]" value={c.op} onChange={(e) => set(i, { op: e.target.value })}>
              {Object.entries(ops).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
            {!['vazio', 'preenchido'].includes(c.op) && (
              <Input className="flex-1" value={c.valor} onChange={(e) => set(i, { valor: e.target.value })}
                placeholder={c.op === 'em' ? 'valores separados por vírgula' : /^DT_/.test(c.campo) ? 'dd/mm/aaaa' : 'valor'} />
            )}
            <Button size="icon-sm" variant="ghost" onClick={() => setDraft((d) => d.filter((_, j) => j !== i))}><X className="h-4 w-4" /></Button>
          </div>
        ))}
        <div className="flex items-center justify-between pt-1">
          <Button size="sm" variant="ghost" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setDraft((d) => [...d, { campo: fields[0] ?? '', op: '=', valor: '' }])}>Condição</Button>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => { onChange([]); setOpen(false) }}>Remover todas</Button>
            <Button size="sm" variant="primary" onClick={() => { onChange(draft.filter((c) => c.campo)); setOpen(false) }}>Aplicar</Button>
          </div>
        </div>
      </div>
    </Popover>
  )
}

function FileView({ tipo, rs, upd, files }: { tipo: RawTipo; rs: RawState; upd: (p: Partial<RawState>) => void; files: Overview['arquivos'] }) {
  const indexed = files.filter((f) => f.indexado)
  const fid = rs.arquivo && indexed.some((f) => f.id_arquivo === rs.arquivo) ? rs.arquivo : indexed[0]?.id_arquivo
  const registros = rs.registrosArquivo.split(/[,;\s]+/).map((x) => x.trim().toUpperCase()).filter((x) => /^[0-9A-Z]{4}$/.test(x))
  const body = { arquivo: fid, registros, busca: rs.busca }
  const key = `${tipo}|${JSON.stringify(body)}`
  const { data, loading, loadMore } = useInfinite(`/api/raw/${tipo}/lines`, body, key)
  const g = useMemo(() => toGrid(data ? { ...data, labels: { linha_no: 'Linha', reg: 'Registro', unidade: 'Unidade (CNPJ)', linha_original: 'Linha original' } } : null), [data])
  const f = files.find((x) => x.id_arquivo === fid)
  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
        <Select className="min-w-[360px] flex-1" value={fid ?? ''} onChange={(e) => upd({ arquivo: Number(e.target.value) })}>
          {indexed.map((a) => <option key={a.id_arquivo} value={a.id_arquivo}>{fmtComp(a.competencia)} · {fmtCnpj(a.cnpj)} · {a.nome}{a.finalidade === 'RETIFICADORA' ? ' (retificadora)' : ''}</option>)}
        </Select>
        <Input className="w-[240px]" value={rs.registrosArquivo} onChange={(e) => upd({ registrosArquivo: e.target.value })} placeholder="Registros (ex.: C100, C170)" />
        <Button variant="primary" icon={<ArrowDownToLine className="h-4 w-4" />} disabled={!data?.total}
          onClick={() => exportTo(tipo, { ...body, modo: 'arquivo' }, 'xlsx', 'linhas do arquivo')}>Excel</Button>
      </div>
      <div className="px-4 pt-2 text-[12px] text-muted">
        {f && <span className="break-all">{f.caminho_origem}</span>}
        {data?.total != null && <> · {fmtInt(data.total)} linha(s){registros.length ? ` dos registros ${registros.join(', ')}` : ''}</>}
      </div>
      <div className="min-h-0 flex-1 p-2">
        <DataGrid columns={g.columns} rows={g.rows} loading={loading} dense rowHeight={30} onEndReached={loadMore}
          emptyText={indexed.length ? 'Nenhuma linha' : 'Nenhum arquivo com linhas originais guardadas'} />
      </div>
    </Card>
  )
}
