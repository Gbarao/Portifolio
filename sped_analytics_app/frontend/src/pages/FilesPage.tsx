import {
  AlertTriangle, Archive, CheckCircle2, CircleSlash, Copy, DatabaseBackup, FileUp, FolderOpen, HardDrive, History,
  Layers, RefreshCw, RotateCcw, ScrollText, Store, Trash2, UploadCloud,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { DataGrid, sortRows, tableToGrid, useSort } from '../components/DataGrid'
import { Badge, Button, Card, CardHeader, Confirm, Dialog, Field, Input, Progress, Select, Switch, Tip, cx, type Tone } from '../components/ui'
import { api, download, waitJob } from '../lib/api'
import { fmtCnpj, fmtComp, fmtInt } from '../lib/format'
import { useApp } from '../lib/store'
import type { Job, Table } from '../lib/types'

const STATUS: Record<string, { label: string; cls: string; tone: Tone }> = {
  AMBOS: { label: 'SF + EFD', cls: 'bg-ok/15 text-ok', tone: 'ok' },
  SF: { label: 'só SF', cls: 'bg-warn/20 text-warn', tone: 'warn' },
  EC: { label: 'só EFD', cls: 'bg-info/15 text-info', tone: 'info' },
  '': { label: 'ausente', cls: 'bg-bad/10 text-bad', tone: 'bad' },
}
const ACAO_TONE: Record<string, Tone> = { IMPORTADO: 'ok', SUBSTITUIDO: 'info', INDEXADO: 'info', DUPLICADO: 'neutral', IGNORADO: 'warn', ERRO: 'bad', REMOVIDO: 'neutral' }

export function FilesPage() {
  const { meta, dataChanged, options } = useApp()
  const [stats, setStats] = useState<any>(null)
  const [cov, setCov] = useState<{ competencias: string[]; filiais: any[] } | null>(null)
  const [files, setFiles] = useState<Table | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [result, setResult] = useState<any>(null)

  const refresh = useCallback(async () => {
    const [s, c, f] = await Promise.all([api.get('/api/hub/stats'), api.get('/api/hub/coverage'), api.get('/api/hub/files')])
    setStats(s); setCov(c); setFiles(f)
  }, [])
  useEffect(() => { refresh() }, [refresh])

  // retoma acompanhamento de tarefa em andamento (ex.: página recarregada)
  useEffect(() => {
    api.get<Job[]>('/api/jobs').then((js) => { const j = js.find((x) => x.kind === 'import' || x.kind === 'rebuild'); if (j) follow(j.id) }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const follow = useCallback(async (id: string, okMsg?: (j: Job) => string) => {
    const j = await waitJob(id, setJob)
    if (j.status === 'error') toast.error(j.error || 'Falha')
    else {
      if (j.kind === 'import') setResult(j.result)
      toast.success(okMsg ? okMsg(j) : 'Concluído')
    }
    setJob(null)
    await refresh()
    dataChanged()
    return j
  }, [refresh, dataChanged])

  const running = !!job && job.status === 'running'

  return (
    <div className="flex flex-col gap-3 p-3 tall:gap-4 tall:p-5">
      <StatsRow stats={stats} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.25fr_1fr]">
        <ImportCard running={running} job={job} result={result} onStart={(id) => follow(id, (j) => {
          const c = j.result?.contagem || {}
          return `Importação concluída em ${j.result?.segundos}s — ${c.IMPORTADO || 0} importado(s), ${c.SUBSTITUIDO || 0} substituído(s), ${c.INDEXADO ? `${c.INDEXADO} com linhas originais guardadas agora, ` : ''}${c.DUPLICADO || 0} duplicado(s), ${c.ERRO || 0} erro(s)`
        })} />
        <ManageCard running={running} competencias={options?.competencias ?? []} onJob={follow} dataDir={meta.dataDir} />
      </div>
      <CoverageCard cov={cov} />
      <FilesCard files={files} running={running} onJob={follow} />
    </div>
  )
}

function StatsRow({ stats }: { stats: any }) {
  const items = [
    { icon: <ScrollText className="h-4 w-4" />, label: 'Arquivos ativos', value: stats ? `${stats.arquivos}` : '', hint: stats ? `${stats.arquivos_sf} SPED Fiscal · ${stats.arquivos_ec} EFD-Contribuições` : '' },
    { icon: <Layers className="h-4 w-4" />, label: 'Linhas consolidadas', value: stats ? fmtInt(stats.linhas_fato) : '' },
    { icon: <Store className="h-4 w-4" />, label: 'Filiais', value: stats ? fmtInt(stats.filiais) : '' },
    { icon: <History className="h-4 w-4" />, label: 'Competências', value: stats ? fmtInt(stats.competencias) : '' },
    { icon: <HardDrive className="h-4 w-4" />, label: 'Banco local', value: stats ? `${(stats.db_mb).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB` : '', hint: stats ? `+ ${(stats.parquet_mb).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB de cache Parquet` : '' },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      {items.map((i) => (
        <div key={i.label} className="rounded-xl border bg-panel px-4 py-3 shadow-card">
          <div className="flex items-center gap-2 text-[11.5px] font-medium uppercase tracking-wide text-muted">{i.icon}{i.label}</div>
          {stats ? <div className="num mt-1 text-[20px] font-semibold tracking-tight">{i.value}</div> : <div className="skeleton mt-2 h-6 w-20" />}
          {i.hint && <div className="mt-0.5 text-[11.5px] text-muted">{i.hint}</div>}
        </div>
      ))}
    </div>
  )
}

function ImportCard({ running, job, result, onStart }: { running: boolean; job: Job | null; result: any; onStart: (id: string) => void }) {
  const { meta } = useApp()
  const [path, setPath] = useState('')
  const [workers, setWorkers] = useState(meta.workers)
  const [drag, setDrag] = useState(false)
  const [upload, setUpload] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const start = async () => {
    try { const r = await api.post('/api/hub/import', { paths: [path], workers }); onStart(r.job) } catch (e: any) { toast.error(e.message) }
  }
  const pick = async () => {
    const r = await api.get('/api/native/pick-folder')
    if (r.path) setPath(r.path)
  }
  const sendFiles = async (list: FileList | File[]) => {
    const arr = Array.from(list).filter((f) => /\.txt$/i.test(f.name))
    if (!arr.length) { toast.error('Selecione arquivos .txt do SPED'); return }
    setUpload(0)
    try {
      const r = await api.upload('/api/hub/upload', arr, setUpload)
      setUpload(null); onStart(r.job)
    } catch (e: any) { setUpload(null); toast.error(e.message) }
  }

  return (
    <Card>
      <CardHeader icon={<FileUp className="h-5 w-5" />} title="Importar arquivos SPED"
        subtitle="SPED Fiscal e EFD-Contribuições são identificados pelo registro 0000. Subpastas incluídas; duplicados e retificadoras são tratados automaticamente." />
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Pasta ou arquivo no seu computador" className="min-w-[280px] flex-1">
            <Input value={path} onChange={(e) => setPath(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && path && start()}
              placeholder="C:\SPED\2024   ou   /home/usuario/sped" icon={<FolderOpen className="h-4 w-4" />} />
          </Field>
          {meta.native && <Button onClick={pick} icon={<FolderOpen className="h-4 w-4" />}>Procurar…</Button>}
          <Field label="Processos">
            <Select value={workers} onChange={(e) => setWorkers(Number(e.target.value))}>
              {Array.from({ length: Math.max(1, meta.cpuCount) }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </Field>
          <Button variant="primary" disabled={!path.trim() || running} loading={running && job?.kind === 'import'} onClick={start} icon={<UploadCloud className="h-4 w-4" />}>Importar</Button>
        </div>

        <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (!running) sendFiles(e.dataTransfer.files) }}
          onClick={() => !running && inputRef.current?.click()}
          className={cx('flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors',
            drag ? 'border-accent bg-accent/5' : 'hover:border-muted/50 hover:bg-sunken/50')}>
          <UploadCloud className={cx('h-7 w-7', drag ? 'text-accent' : 'text-muted')} />
          <div className="text-[13px] font-medium">Arraste os arquivos .txt aqui ou clique para selecionar</div>
          <div className="text-[12px] text-muted">Os arquivos são copiados para o cofre local antes da leitura. Para volumes de vários GB, prefira informar a pasta acima.</div>
          <input ref={inputRef} type="file" multiple accept=".txt,.TXT" className="hidden" onChange={(e) => e.target.files && sendFiles(e.target.files)} />
        </div>

        {(upload != null || running) && (
          <div className="space-y-1.5 rounded-lg bg-sunken/60 p-3">
            <div className="flex justify-between text-[12.5px]">
              <span className="font-medium">{upload != null ? 'Enviando arquivos…' : job?.msg}</span>
              <span className="num text-muted">{Math.round(((upload ?? job?.frac) || 0) * 100)}%</span>
            </div>
            <Progress value={(upload ?? job?.frac) || 0} />
          </div>
        )}

        {result && !running && <ImportResult result={result} />}
      </div>
    </Card>
  )
}

function ImportResult({ result }: { result: any }) {
  const c = result.contagem || {}
  return (
    <div className="rounded-lg border">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2 text-[12.5px]">
        <span className="font-medium">Última importação · {result.segundos}s</span>
        {Object.entries(c).filter(([, n]) => (n as number) > 0).map(([k, n]) => <Badge key={k} tone={ACAO_TONE[k]}>{k.toLowerCase()} {String(n)}</Badge>)}
        {result.competencias?.length > 0 && <span className="text-muted">· reconsolidado: {result.competencias.map(fmtComp).join(', ')}</span>}
      </div>
      <div className="max-h-[180px] overflow-auto">
        {result.resultados.map((r: any, i: number) => (
          <div key={i} className="flex items-start gap-2 border-b border-line/60 px-3 py-1.5 text-[12.5px] last:border-0">
            <Badge tone={ACAO_TONE[r.acao]} className="mt-0.5 w-[92px] justify-center">{r.acao.toLowerCase()}</Badge>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{r.arquivo}</div>
              <div className="truncate text-[11.5px] text-muted">{[r.tipo === 'ICMS_IPI' ? 'SPED Fiscal' : r.tipo === 'CONTRIB' ? 'EFD-Contribuições' : r.tipo, fmtCnpj(r.cnpj), r.competencia && fmtComp(r.competencia), r.mensagem].filter(Boolean).join(' · ')}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ManageCard({ running, competencias, onJob, dataDir }: { running: boolean; competencias: string[]; onJob: (id: string, m?: (j: Job) => string) => Promise<Job>; dataDir: string }) {
  const [sel, setSel] = useState<string[]>([])
  const [tipo, setTipo] = useState('')
  const [confirm, setConfirm] = useState<null | 'comps' | 'rebuild' | 'restore'>(null)
  const [parquet, setParquet] = useState(false)
  const [restorePath, setRestorePath] = useState('')
  const [logOpen, setLogOpen] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const call = async (key: string, url: string, body: any, msg: (j: Job) => string) => {
    setBusy(key)
    try { const r = await api.post(url, body); setConfirm(null); const j = await onJob(r.job, msg); return j } catch (e: any) { toast.error(e.message) } finally { setBusy(null) }
  }
  const backup = async () => {
    const j = await call('backup', '/api/hub/backup', { incluirParquet: parquet }, (j) => `Backup gerado: ${j.result?.name}`)
    if (j?.status === 'done') download(j.result.url)
  }

  return (
    <Card>
      <CardHeader icon={<DatabaseBackup className="h-5 w-5" />} title="Gestão da base" subtitle={<span className="break-all">Cofre local: {dataDir}</span>}
        actions={<Button size="sm" variant="ghost" icon={<FolderOpen className="h-4 w-4" />} onClick={() => api.post('/api/open-folder', { path: dataDir })}>Abrir</Button>} />
      <div className="divide-y">
        <section className="space-y-2 p-4">
          <div className="text-[12.5px] font-semibold">Remover competências</div>
          <div className="flex max-h-[84px] flex-wrap gap-1 overflow-auto">
            {competencias.map((c) => {
              const on = sel.includes(c)
              return <button key={c} onClick={() => setSel(on ? sel.filter((x) => x !== c) : [...sel, c])}
                className={cx('rounded-md border px-2 py-0.5 text-[12px]', on ? 'border-bad bg-bad/10 text-bad' : 'hover:bg-sunken')}>{fmtComp(c)}</button>
            })}
            {!competencias.length && <span className="text-[12px] text-muted">Nenhuma competência</span>}
          </div>
          <div className="flex gap-2">
            <Select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">SPED Fiscal e EFD</option><option value="ICMS_IPI">Só SPED Fiscal</option><option value="CONTRIB">Só EFD-Contribuições</option>
            </Select>
            <Button variant="outline" className="text-bad" disabled={!sel.length || running} icon={<Trash2 className="h-4 w-4" />} onClick={() => setConfirm('comps')}>Remover</Button>
          </div>
        </section>
        <section className="flex flex-wrap items-center gap-3 p-4">
          <div className="flex-1 text-[12.5px]"><div className="font-semibold">Backup</div><div className="text-muted">Arquivo .zip com o banco, filtros e snapshots.</div></div>
          <Switch checked={parquet} onChange={setParquet} label="Incluir cache Parquet" />
          <Button icon={<Archive className="h-4 w-4" />} loading={busy === 'backup'} onClick={backup}>Gerar backup</Button>
        </section>
        <section className="flex flex-wrap items-end gap-2 p-4">
          <Field label="Restaurar backup (.zip)" className="min-w-[220px] flex-1"><Input value={restorePath} onChange={(e) => setRestorePath(e.target.value)} placeholder="Caminho do arquivo .zip" /></Field>
          <Button disabled={!restorePath.trim() || running} icon={<RotateCcw className="h-4 w-4" />} onClick={() => setConfirm('restore')}>Restaurar</Button>
        </section>
        <section className="flex flex-wrap gap-2 p-4">
          <Button disabled={running} icon={<RefreshCw className="h-4 w-4" />} onClick={() => setConfirm('rebuild')}>Reconsolidar toda a base</Button>
          <Button variant="ghost" icon={<ScrollText className="h-4 w-4" />} onClick={() => setLogOpen(true)}>Log de importação</Button>
        </section>
      </div>

      <Confirm open={confirm === 'comps'} onOpenChange={(o) => !o && setConfirm(null)} title="Remover competências" danger confirmLabel="Remover" loading={busy === 'comps'}
        onConfirm={() => call('comps', '/api/hub/remove-competencias', { competencias: sel, tipo: tipo || null }, () => 'Competências removidas').then(() => setSel([]))}>
        Remover {tipo === 'ICMS_IPI' ? 'os arquivos do SPED Fiscal' : tipo === 'CONTRIB' ? 'os arquivos da EFD-Contribuições' : 'todos os arquivos'} de <b>{sel.map(fmtComp).join(', ')}</b>? Os dados consolidados desses meses serão refeitos.
      </Confirm>
      <Confirm open={confirm === 'rebuild'} onOpenChange={(o) => !o && setConfirm(null)} title="Reconsolidar toda a base" confirmLabel="Reconsolidar" loading={busy === 'rebuild'}
        onConfirm={() => call('rebuild', '/api/hub/rebuild', {}, (j) => `${fmtInt(j.result?.linhas)} linhas consolidadas em ${Math.round(j.result?.segundos)}s`)}>
        Refaz o cruzamento SPED Fiscal × EFD-Contribuições de todas as competências a partir dos dados importados. Em bases grandes pode levar alguns minutos.
      </Confirm>
      <Confirm open={confirm === 'restore'} onOpenChange={(o) => !o && setConfirm(null)} title="Restaurar backup" danger confirmLabel="Restaurar" loading={busy === 'restore'}
        onConfirm={() => call('restore', '/api/hub/restore', { path: restorePath }, () => 'Base restaurada')}>
        A base atual será substituída pelo backup. Uma cópia de segurança da base atual é mantida na pasta de dados.
      </Confirm>
      <LogDialog open={logOpen} onOpenChange={setLogOpen} />
    </Card>
  )
}

function LogDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [t, setT] = useState<Table | null>(null)
  useEffect(() => { if (open) api.get('/api/hub/log').then(setT) }, [open])
  const g = useMemo(() => tableToGrid(t, { widths: { data: 150, acao: 120, arquivo: 420, mensagem: 520 } }), [t])
  const cols = g.columns.map((c) => c.key === 'acao' ? { ...c, render: (r: any) => <Badge tone={ACAO_TONE[r.cells.acao]}>{String(r.cells.acao).toLowerCase()}</Badge> } : c)
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Log de importação" full>
      <div className="h-full min-h-[400px]"><DataGrid columns={cols} rows={g.rows} loading={!t} dense /></div>
    </Dialog>
  )
}

function CoverageCard({ cov }: { cov: { competencias: string[]; filiais: any[] } | null }) {
  const gaps = cov ? cov.filiais.reduce((a, f) => a + cov.competencias.filter((c) => f.status[c] !== 'AMBOS').length, 0) : 0
  return (
    <Card>
      <CardHeader icon={<CheckCircle2 className="h-5 w-5" />} title="Matriz de cobertura fiscal"
        subtitle={cov ? `${cov.filiais.length} estabelecimento(s) × ${cov.competencias.length} competência(s) · ${gaps ? `${gaps} lacuna(s)` : 'cobertura completa'}` : 'Carregando…'}
        actions={<div className="flex gap-1.5">{Object.entries(STATUS).map(([k, s]) => <span key={k} className={cx('rounded-md px-2 py-0.5 text-[11.5px] font-medium', s.cls)}>{s.label}</span>)}</div>} />
      <div className="overflow-auto p-4">
        {cov && cov.filiais.length === 0 && <div className="py-8 text-center text-[13px] text-muted">Nenhum arquivo importado ainda.</div>}
        {cov && cov.filiais.length > 0 && (
          <table className="border-separate border-spacing-[3px] text-[12px]">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-panel px-2 text-left font-medium text-muted">Estabelecimento</th>
                {cov.competencias.map((c) => <th key={c} className="min-w-[64px] px-1 text-center font-medium text-muted">{fmtComp(c)}</th>)}
              </tr>
            </thead>
            <tbody>
              {cov.filiais.map((f) => (
                <tr key={f.cnpj}>
                  <td className="sticky left-0 z-10 bg-panel pr-3">
                    <div className="max-w-[260px] truncate font-medium">{f.nome || '—'}</div>
                    <div className="num font-mono text-[11px] text-muted">{fmtCnpj(f.cnpj)} {f.uf && `· ${f.uf}`}</div>
                  </td>
                  {cov.competencias.map((c) => {
                    const s = STATUS[f.status[c] ?? ''] ?? STATUS['']
                    return (
                      <td key={c} className="p-0">
                        <Tip content={`${fmtComp(c)}: ${s.label}`}>
                          <div className={cx('flex h-8 items-center justify-center rounded-md text-[11px] font-medium', s.cls)}>
                            {f.status[c] === 'AMBOS' ? <CheckCircle2 className="h-4 w-4" /> : f.status[c] === 'SF' ? 'SF' : f.status[c] === 'EC' ? 'EFD' : <CircleSlash className="h-3.5 w-3.5" />}
                          </div>
                        </Tip>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  )
}

function FilesCard({ files, running, onJob }: { files: Table | null; running: boolean; onJob: (id: string, m?: (j: Job) => string) => Promise<Job> }) {
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sort, toggleSort] = useSort(null)
  const g = useMemo(() => tableToGrid(files, { idCol: 'id_arquivo', hide: ['ativo', 'substituido_por'], widths: { id_arquivo: 64, tipo_sped: 150, cnpj: 168, nome: 240, competencia: 110, finalidade: 120, documentos: 90, linhas: 100, tamanho_mb: 80, data_importacao: 150, caminho_origem: 420 } }), [files])
  const cols = g.columns.map((c) => {
    if (c.key === 'tipo_sped') return { ...c, render: (r: any) => <Badge tone={r.cells.tipo_sped === 'ICMS_IPI' ? 'accent' : 'info'}>{r.cells.tipo_sped === 'ICMS_IPI' ? 'SPED Fiscal' : 'EFD-Contribuições'}</Badge> }
    if (c.key === 'finalidade') return { ...c, render: (r: any) => r.cells.finalidade === 'RETIFICADORA' ? <Badge tone="warn">retificadora</Badge> : <span className="text-muted">original</span> }
    if (c.key === 'competencia') return { ...c, render: (r: any) => fmtComp(r.cells.competencia) }
    return c
  })
  const remove = async () => {
    setBusy(true)
    try { const r = await api.post('/api/hub/remove-files', { ids: [...checked].map(Number) }); setConfirm(false); await onJob(r.job, () => 'Arquivos removidos'); setChecked(new Set()) }
    catch (e: any) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <Card>
      <CardHeader icon={<Copy className="h-5 w-5" />} title="Arquivos importados" subtitle={files ? `${files.rows.length} arquivo(s) ativo(s)` : ''}
        actions={<Button variant="outline" className="text-bad" disabled={!checked.size || running} icon={<Trash2 className="h-4 w-4" />} onClick={() => setConfirm(true)}>Remover {checked.size ? `(${checked.size})` : ''}</Button>} />
      <div className="h-[380px] p-3">
        <DataGrid columns={cols} rows={sortRows(g.rows, sort)} loading={!files} checkable checked={checked} onCheck={setChecked} sort={sort} onSort={toggleSort} dense
          emptyText="Nenhum arquivo importado" />
      </div>
      <Confirm open={confirm} onOpenChange={setConfirm} title="Remover arquivos" danger confirmLabel="Remover" loading={busy} onConfirm={remove}>
        <div className="flex gap-2"><AlertTriangle className="h-5 w-5 shrink-0 text-warn" />Remover {checked.size} arquivo(s) e seus dados? As competências afetadas (e as ligadas a elas pela chave da nota) serão reconsolidadas.</div>
      </Confirm>
    </Card>
  )
}

