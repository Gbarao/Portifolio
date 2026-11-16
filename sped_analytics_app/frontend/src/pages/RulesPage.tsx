import { Bookmark, BookmarkPlus, Calculator, Eraser, FolderTree, Pencil, Play, Plus, ShieldCheck, ShieldAlert, Snowflake, Trash2, X, Zap } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { DataGrid, tableToGrid } from '../components/DataGrid'
import { Badge, Button, Card, CardHeader, Confirm, Dialog, Empty, Field, Input, Select, Switch, cx } from '../components/ui'
import { api, download } from '../lib/api'
import { fmtBRL, fmtInt } from '../lib/format'
import { useApp } from '../lib/store'
import type { Rule, RuleGroup, SavedFilter, Table } from '../lib/types'

let seq = 0
const uid = () => `r${Date.now().toString(36)}${(seq++).toString(36)}`
const isGroup = (n: any): n is RuleGroup => n && Array.isArray(n.rules)
const withIds = (n: any): any => (isGroup(n) ? { ...n, id: uid(), rules: n.rules.map(withIds) } : { ...n, id: uid() })
const strip = (n: any): any => (isGroup(n) ? { op: n.op, rules: n.rules.map(strip) } : { field: n.field, operator: n.operator, value: n.value })

export function RulesPage() {
  const { state, set, meta } = useApp()
  const [tree, setTree] = useState<RuleGroup>(() => withIds(state.rules?.rules ? state.rules : { op: 'AND', rules: [] }))
  const [preview, setPreview] = useState<{ ok: boolean; sql?: string; params?: string[]; description?: string; error?: string } | null>(null)
  const [test, setTest] = useState<any>(null)
  const [testing, setTesting] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)

  useEffect(() => { setTree(withIds(state.rules?.rules ? state.rules : { op: 'AND', rules: [] })) }, [JSON.stringify(state.rules)])

  const clean = useMemo(() => strip(tree), [tree])
  useEffect(() => {
    setTest(null)
    const t = setTimeout(() => api.post('/api/rules/preview', { rules: clean }).then(setPreview).catch(() => {}), 200)
    return () => clearTimeout(t)
  }, [JSON.stringify(clean)])

  const update = (fn: (g: RuleGroup) => void) => setTree((t) => { const c = structuredClone(t); fn(c); return c })
  const find = (g: RuleGroup, id: string): any => { if (g.id === id) return g; for (const r of g.rules) { if ((r as any).id === id) return r; if (isGroup(r)) { const f = find(r, id); if (f) return f } } return null }
  const parentOf = (g: RuleGroup, id: string): RuleGroup | null => { for (const r of g.rules) { if ((r as any).id === id) return g; if (isGroup(r)) { const p = parentOf(r, id); if (p) return p } } return null }

  const fields = meta.fields
  const fieldMap = Object.fromEntries(fields.map((f) => [f.key, f]))
  const newRule = (): Rule => ({ id: uid(), field: 'cst_pis', operator: 'em', value: '' })

  const runTest = async () => {
    if (!preview?.ok) return
    setTesting(true)
    try { setTest(await api.post('/api/rules/test', { gf: state.gf, rules: clean })) } catch (e: any) { toast.error(e.message) } finally { setTesting(false) }
  }
  const apply = () => {
    if (!preview?.ok) { toast.error(preview?.error || 'Regra inválida'); return }
    set({ rules: clean, appliedFilterName: '', page: 'analise' })
  }

  const renderGroup = (g: RuleGroup, depth: number): JSX.Element => (
    <div key={g.id} className={cx('space-y-2 rounded-xl border p-3', depth ? 'border-dashed bg-sunken/40' : 'bg-panel')}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-semibold uppercase tracking-wide text-muted">{depth ? 'Grupo' : 'Atender'}</span>
        <div className="inline-flex rounded-lg bg-sunken p-0.5">
          {(['AND', 'OR'] as const).map((op) => (
            <button key={op} onClick={() => update((t) => { find(t, g.id!).op = op })}
              className={cx('rounded-md px-2.5 py-1 text-[12px] font-medium', g.op === op ? 'bg-panel shadow-sm' : 'text-muted')}>
              {op === 'AND' ? 'todas (E)' : 'qualquer (OU)'}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <Button size="sm" variant="ghost" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => update((t) => { find(t, g.id!).rules.push(newRule()) })}>Condição</Button>
        {depth < 2 && <Button size="sm" variant="ghost" icon={<FolderTree className="h-3.5 w-3.5" />} onClick={() => update((t) => { find(t, g.id!).rules.push({ id: uid(), op: 'OR', rules: [newRule()] }) })}>Grupo</Button>}
        {depth > 0 && <Button size="icon-sm" variant="ghost" className="text-bad" onClick={() => update((t) => { const p = parentOf(t, g.id!); if (p) p.rules = p.rules.filter((x) => (x as any).id !== g.id) })}><Trash2 className="h-4 w-4" /></Button>}
      </div>
      {g.rules.length === 0 && <div className="rounded-lg border border-dashed px-3 py-4 text-center text-[12.5px] text-muted">Nenhuma condição. Clique em “Condição” para começar.</div>}
      {g.rules.map((r, i) => (
        <div key={(r as any).id} className="flex items-start gap-2">
          <span className="mt-2 w-7 shrink-0 text-right text-[11px] font-semibold uppercase text-muted">{i === 0 ? '' : g.op === 'AND' ? 'e' : 'ou'}</span>
          <div className="min-w-0 flex-1">
            {isGroup(r) ? renderGroup(r, depth + 1) : (
              <div className="flex flex-wrap items-center gap-2">
                <Select className="w-[250px]" value={r.field} onChange={(e) => update((t) => { const n = find(t, (r as any).id); n.field = e.target.value; const ops = meta.opsByType[fieldMap[e.target.value]?.type ?? 'text']; if (!ops.includes(n.operator)) n.operator = ops[0] })}>
                  {['text', 'number', 'date', 'bool'].map((tp) => (
                    <optgroup key={tp} label={{ text: 'Texto / códigos', number: 'Valores e alíquotas', date: 'Datas', bool: 'Indicadores' }[tp]}>
                      {fields.filter((f) => f.type === tp).sort((a, b) => a.label.localeCompare(b.label)).map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                    </optgroup>
                  ))}
                </Select>
                <Select className="w-[170px]" value={r.operator} onChange={(e) => update((t) => { find(t, (r as any).id).operator = e.target.value })}>
                  {(meta.opsByType[fieldMap[r.field]?.type ?? 'text'] || []).map((o) => <option key={o} value={o}>{meta.operators[o]}</option>)}
                </Select>
                {!['vazio', 'preenchido'].includes(r.operator) && (
                  fieldMap[r.field]?.type === 'bool'
                    ? <Select className="w-[120px]" value={String(r.value || 'sim')} onChange={(e) => update((t) => { find(t, (r as any).id).value = e.target.value })}><option value="sim">Sim</option><option value="nao">Não</option></Select>
                    : <Input className="min-w-[180px] flex-1" value={Array.isArray(r.value) ? r.value.join(', ') : r.value ?? ''}
                        placeholder={['em', 'nao_em'].includes(r.operator) ? 'valores separados por vírgula' : r.operator === 'entre' ? 'a; b' : fieldMap[r.field]?.type === 'date' ? 'dd/mm/aaaa' : 'valor'}
                        onChange={(e) => update((t) => { find(t, (r as any).id).value = e.target.value })} />
                )}
                <Button size="icon-sm" variant="ghost" className="text-muted hover:text-bad" onClick={() => update((t) => { const p = parentOf(t, (r as any).id); if (p) p.rules = p.rules.filter((x) => (x as any).id !== (r as any).id) })}><X className="h-4 w-4" /></Button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="grid grid-cols-1 gap-4 p-5 2xl:grid-cols-[1fr_420px]">
      <div className="space-y-4">
        <Card>
          <CardHeader icon={<Zap className="h-5 w-5" />} title="Construtor de regras"
            subtitle="Combine condições sobre qualquer coluna da base consolidada. As regras se somam aos filtros globais da Análise."
            actions={<Button size="sm" variant="ghost" icon={<Eraser className="h-4 w-4" />} onClick={() => setTree({ id: uid(), op: 'AND', rules: [] })}>Limpar</Button>} />
          <div className="space-y-3 p-4">
            {renderGroup(tree, 0)}
            <div className={cx('rounded-lg border px-3 py-2.5 text-[12.5px]', preview && !preview.ok ? 'border-bad/40 bg-bad/5' : 'bg-sunken/50')}>
              {preview?.ok ? (
                <>
                  <div className="font-medium">{preview.description || 'Sem condições (todas as linhas)'}</div>
                  <div className="mt-1 break-all font-mono text-[11.5px] text-muted">WHERE {preview.sql}{preview.params?.length ? `   · parâmetros: ${preview.params.join(', ')}` : ''}</div>
                </>
              ) : <div className="text-bad">{preview?.error || '…'}</div>}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" icon={<Play className="h-4 w-4" />} disabled={!preview?.ok} onClick={apply}>Aplicar na análise</Button>
              <Button icon={<Calculator className="h-4 w-4" />} loading={testing} disabled={!preview?.ok} onClick={runTest}>Testar</Button>
              <Button icon={<BookmarkPlus className="h-4 w-4" />} disabled={!preview?.ok} onClick={() => setSaveOpen(true)}>Salvar filtro</Button>
              {test && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg bg-accent/[0.06] px-3 py-1.5 text-[12.5px]">
                  <span><b>{fmtInt(test.totals.n_linhas)}</b> linhas</span>
                  <span>Valor contábil <b>{fmtBRL(test.totals.vl_contabil)}</b></span>
                  <span>ICMS <b>{fmtBRL(test.totals.vl_icms)}</b></span>
                  <span>PIS <b>{fmtBRL(test.totals.vl_pis)}</b></span>
                  <span>COFINS <b>{fmtBRL(test.totals.vl_cofins)}</b></span>
                  <span className="text-muted">({test.ms} ms, com filtros globais)</span>
                </div>
              )}
            </div>
          </div>
        </Card>
        <Examples onUse={(r) => setTree(withIds(r))} />
      </div>
      <div className="space-y-4">
        <Library />
        <Snapshots />
      </div>
      <SaveDialog open={saveOpen} onOpenChange={setSaveOpen} rules={clean} />
    </div>
  )
}

function Examples({ onUse }: { onUse: (r: RuleGroup) => void }) {
  const ex: [string, string, RuleGroup][] = [
    ['Créditos básicos de PIS/COFINS', 'CST PIS 50 a 56', { op: 'AND', rules: [{ field: 'cst_pis', operator: 'em', value: '50,51,52,53,54,55,56' }] }],
    ['Insumo com ICMS e sem PIS', 'Possível crédito de PIS/COFINS não aproveitado', { op: 'AND', rules: [{ field: 'tipo_item', operator: 'em', value: '01,02' }, { field: 'vl_icms', operator: '>', value: '0' }, { field: 'vl_pis', operator: 'vazio', value: '' }] }],
    ['Uso e consumo / ativo', 'TIPO_ITEM 07 ou 08', { op: 'AND', rules: [{ field: 'tipo_item', operator: 'em', value: '07,08' }] }],
    ['Somente na EFD', 'Créditos sem correspondência no SPED Fiscal', { op: 'AND', rules: [{ field: 'nivel_cruzamento_efd', operator: '=', value: 'EC_SEM_PAR' }] }],
    ['Compras com ICMS-ST', 'Valor de ICMS-ST maior que zero', { op: 'AND', rules: [{ field: 'vl_icms_st', operator: '>', value: '0' }] }],
    ['Importação', 'CFOP iniciado por 3', { op: 'AND', rules: [{ field: 'cfop', operator: 'comeca_com', value: '3' }] }],
  ]
  return (
    <Card>
      <CardHeader title="Modelos prontos" subtitle="Clique para carregar no construtor e ajustar." />
      <div className="grid grid-cols-1 gap-2 p-3 md:grid-cols-2 xl:grid-cols-3">
        {ex.map(([t, d, r]) => (
          <button key={t} onClick={() => onUse(r)} className="rounded-lg border px-3 py-2 text-left transition-colors hover:border-accent/50 hover:bg-accent/[0.04]">
            <div className="text-[13px] font-medium">{t}</div><div className="text-[12px] text-muted">{d}</div>
          </button>
        ))}
      </div>
    </Card>
  )
}

function SaveDialog({ open, onOpenChange, rules }: { open: boolean; onOpenChange: (o: boolean) => void; rules: RuleGroup }) {
  const { state, filters, reloadLibrary } = useApp()
  const [nome, setNome] = useState('')
  const [cat, setCat] = useState('Geral')
  const [incGlobal, setIncGlobal] = useState(true)
  const [incView, setIncView] = useState(true)
  const [busy, setBusy] = useState(false)
  const cats = Array.from(new Set(['Geral', 'PIS/COFINS', 'ICMS', 'Auditoria', ...filters.map((f) => f.categoria)]))
  const save = async () => {
    setBusy(true)
    try {
      const definicao: any = { rules, global: incGlobal ? state.gf : {} }
      if (incView) definicao.view = { hierarchy: state.hierarchy, mode: state.mode, metrics: state.metrics }
      await api.post('/api/filters', { nome, categoria: cat, definicao })
      toast.success('Filtro salvo'); onOpenChange(false); setNome(''); reloadLibrary()
    } catch (e: any) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Salvar filtro" description="Fica disponível na barra lateral para aplicar com um clique."
      footer={<><Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button><Button variant="primary" disabled={!nome.trim()} loading={busy} onClick={save}>Salvar</Button></>}>
      <div className="space-y-3">
        <Field label="Nome"><Input autoFocus value={nome} onChange={(e) => setNome(e.target.value)} placeholder="ex.: Créditos de insumos SP" /></Field>
        <Field label="Categoria">
          <Input list="cats" value={cat} onChange={(e) => setCat(e.target.value)} />
          <datalist id="cats">{cats.map((c) => <option key={c} value={c} />)}</datalist>
        </Field>
        <Switch checked={incGlobal} onChange={setIncGlobal} label="Incluir filtros globais atuais (período, filiais, fornecedores…)" />
        <Switch checked={incView} onChange={setIncView} label="Incluir hierarquia, modo e colunas" />
      </div>
    </Dialog>
  )
}

function Library() {
  const { filters, applyPreset, reloadLibrary, set } = useApp()
  const [del, setDel] = useState<SavedFilter | null>(null)
  const groups = useMemo(() => {
    const m: Record<string, SavedFilter[]> = {}
    filters.forEach((f) => { (m[f.categoria] ||= []).push(f) })
    return Object.entries(m)
  }, [filters])
  return (
    <Card>
      <CardHeader icon={<Bookmark className="h-5 w-5" />} title="Filtros salvos" subtitle="Aplicar com um clique" />
      <div className="max-h-[420px] overflow-auto p-2">
        {!filters.length && <Empty title="Nenhum filtro salvo">Monte uma regra e clique em “Salvar filtro”.</Empty>}
        {groups.map(([cat, list]) => (
          <div key={cat} className="mb-1">
            <div className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{cat}</div>
            {list.map((f) => (
              <div key={f.id} className="group flex items-center gap-1 rounded-lg px-2 py-1.5 hover:bg-sunken">
                <button className="flex min-w-0 flex-1 items-center gap-2 text-left text-[13px]" onClick={() => applyPreset(f)}>
                  <Zap className="h-3.5 w-3.5 shrink-0 text-accent" /><span className="truncate">{f.nome}</span>
                </button>
                <Button size="icon-sm" variant="ghost" className="opacity-0 group-hover:opacity-100" title="Editar regras"
                  onClick={() => set({ rules: (f.definicao.rules as any) || { op: 'AND', rules: [] }, appliedFilterName: f.nome })}><Pencil className="h-3.5 w-3.5" /></Button>
                <Button size="icon-sm" variant="ghost" className="text-muted opacity-0 hover:text-bad group-hover:opacity-100" onClick={() => setDel(f)}><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            ))}
          </div>
        ))}
      </div>
      <Confirm open={!!del} onOpenChange={(o) => !o && setDel(null)} title="Excluir filtro" danger confirmLabel="Excluir"
        onConfirm={async () => { await api.del(`/api/filters/${del!.id}`); setDel(null); reloadLibrary() }}>
        Excluir o filtro “{del?.nome}”?
      </Confirm>
    </Card>
  )
}

function Snapshots() {
  const { snaps } = useApp()
  const [open, setOpen] = useState<number | null>(null)
  return (
    <Card>
      <CardHeader icon={<Snowflake className="h-5 w-5" />} title="Análises congeladas" subtitle="Snapshots imutáveis com hash de integridade" />
      <div className="max-h-[420px] overflow-auto p-2">
        {!snaps.length && <Empty title="Nenhum snapshot">Use “Congelar análise” na tela de Análise.</Empty>}
        {snaps.map((s) => (
          <button key={s.id} onClick={() => setOpen(s.id)} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-sunken">
            <Snowflake className="h-4 w-4 shrink-0 text-info" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium">#{s.id} {s.nome}</div>
              <div className="text-[11.5px] text-muted">{s.criado_em} · {fmtInt(s.linhas)} linhas</div>
            </div>
          </button>
        ))}
      </div>
      {open != null && <SnapshotViewer id={open} onClose={() => setOpen(null)} />}
    </Card>
  )
}

export function SnapshotViewer({ id, onClose }: { id: number; onClose: () => void }) {
  const { set, reloadLibrary } = useApp()
  const [d, setD] = useState<(Table & { meta: any; ok: boolean; total: number }) | null>(null)
  const [del, setDel] = useState(false)
  useEffect(() => { api.get(`/api/snapshots/${id}`).then(setD).catch((e) => toast.error(e.message)) }, [id])
  const g = useMemo(() => tableToGrid(d, { sticky: 1 }), [d])
  const exp = async () => { const r = await api.post(`/api/snapshots/${id}/export`); toast.success('Excel gerado', { description: r.path }); download(r.url) }
  const restore = () => {
    const st = d?.meta?.contexto?.state
    if (!st) return
    set({ gf: st.gf || {}, rules: st.rules || { op: 'AND', rules: [] }, hierarchy: st.hierarchy, metrics: st.metrics, mode: st.mode, pivotMetric: st.pivotMetric || 'vl_contabil', appliedFilterName: `Snapshot #${id}`, page: 'analise' })
    onClose()
  }
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} full
      title={<span className="flex items-center gap-2">Snapshot #{id} {d?.meta?.nome}
        {d && (d.ok ? <Badge tone="ok"><ShieldCheck className="h-3.5 w-3.5" />íntegro</Badge> : <Badge tone="bad"><ShieldAlert className="h-3.5 w-3.5" />integridade violada</Badge>)}</span>}
      description={d ? `Criado em ${d.meta.criado_em} · ${fmtInt(d.total)} linhas${d.total > d.rows.length ? ` (exibindo ${fmtInt(d.rows.length)})` : ''}` : 'Carregando…'}
      footer={<>
        <Button variant="ghost" className="mr-auto text-bad" icon={<Trash2 className="h-4 w-4" />} onClick={() => setDel(true)}>Excluir</Button>
        <Button onClick={restore} disabled={!d?.meta?.contexto?.state}>Restaurar contexto na análise</Button>
        <Button variant="primary" onClick={exp}>Exportar Excel</Button>
      </>}>
      <div className="flex h-full flex-col gap-3">
        {d?.meta?.anotacoes && <div className="whitespace-pre-wrap rounded-lg bg-sunken/60 px-3 py-2 text-[12.5px]">{d.meta.anotacoes}</div>}
        <div className="min-h-[300px] flex-1"><DataGrid columns={g.columns} rows={g.rows} loading={!d} dense /></div>
      </div>
      <Confirm open={del} onOpenChange={setDel} title="Excluir snapshot" danger confirmLabel="Excluir"
        onConfirm={async () => { await api.del(`/api/snapshots/${id}`); setDel(false); reloadLibrary(); onClose() }}>Excluir definitivamente o snapshot #{id}?</Confirm>
    </Dialog>
  )
}
