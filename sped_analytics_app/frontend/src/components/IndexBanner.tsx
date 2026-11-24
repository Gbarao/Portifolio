import { FolderOpen, RefreshCw, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api, waitJob } from '../lib/api'
import { fmtInt } from '../lib/format'
import { useApp } from '../lib/store'
import { Button, Input, Spinner } from './ui'

interface Pending { id: number; tipo: string; caminho: string; competencia: string; cnpj: string; encontrado: boolean }

/**
 * Aviso para arquivos importados antes de o programa guardar as linhas originais (necessárias nas telas SPED Fiscal,
 * EFD-Contribuições, Bloco M e Busca por fornecedor). Permite indexar no caminho da importação ou indicar a pasta
 * onde os TXT estão hoje — cada arquivo é reconhecido pelo conteúdo (hash), não pelo nome.
 */
export function IndexBanner({ tipo, onDone }: { tipo?: 'ICMS_IPI' | 'CONTRIB'; onDone?: () => void }) {
  const { meta, dataVersion, dataChanged } = useApp()
  const [pend, setPend] = useState<Pending[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [askFolder, setAskFolder] = useState(false)
  const [folder, setFolder] = useState('')
  const load = useCallback(() => api.get<Pending[]>('/api/raw/pending').then(setPend).catch(() => setPend([])), [])
  useEffect(() => { load() }, [load, dataVersion])

  if (!pend || pend.length === 0) return null
  const here = tipo ? pend.filter((p) => p.tipo === tipo) : pend
  const missing = pend.filter((p) => !p.encontrado).length

  const run = async (pastas: string[]) => {
    setBusy('Iniciando…')
    try {
      const { job } = await api.post('/api/raw/index', { pastas })
      const j = await waitJob(job, (x) => setBusy(`${x.msg} · ${Math.round(x.frac * 100)}%`))
      if (j.status === 'error') { toast.error(j.error || 'Falha'); return }
      const r = j.result
      const rest = r.nao_encontrados.length + r.alterados.length
      const desc = [
        r.encontrados_na_pasta ? `${fmtInt(r.encontrados_na_pasta)} localizado(s) na pasta indicada.` : '',
        rest ? `${fmtInt(rest)} ainda sem as linhas: ${r.nao_encontrados.length ? `${fmtInt(r.nao_encontrados.length)} não encontrado(s)` : ''}${r.nao_encontrados.length && r.alterados.length ? ' e ' : ''}${r.alterados.length ? `${fmtInt(r.alterados.length)} com conteúdo diferente do importado` : ''}. Indique a pasta onde estão os TXT originais (subpastas incluídas).` : '',
      ].filter(Boolean).join(' ')
      if (r.indexados > 0) toast.success(`${fmtInt(r.indexados)} arquivo(s) indexado(s)`, { description: desc || undefined, duration: 12000 })
      else toast.warning('Nenhum arquivo indexado', { description: desc, duration: 15000 })
      if (r.nao_encontrados.length) setAskFolder(true)
      await load()
      dataChanged()
      onDone?.()
    } catch (e: any) { toast.error(e.message) } finally { setBusy(null) }
  }
  const pick = async () => {
    const r = await api.get('/api/native/pick-folder')
    if (r.path) setFolder(r.path)
  }

  return (
    <div className="space-y-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-3">
        <RefreshCw className="h-4 w-4 shrink-0 text-warn" />
        <span className="min-w-[260px] flex-1">
          <b>{fmtInt(pend.length)}</b> arquivo(s) importado(s) antes de o programa guardar as linhas originais
          {tipo && here.length !== pend.length ? <> ({fmtInt(here.length)} desta tela)</> : null}: o que eles contêm não aparece nesta tela até serem indexados.
          {' '}A consolidação (Análise e Relatório) não é afetada.
          {missing > 0 && <> {fmtInt(missing)} não estão mais no caminho em que foram importados — indique a pasta onde estão hoje.</>}
        </span>
        {busy ? <span className="flex items-center gap-2 text-muted"><Spinner />{busy}</span> : (
          <>
            {missing < pend.length && <Button size="sm" variant="primary" onClick={() => run([])}>Indexar agora</Button>}
            <Button size="sm" variant={missing < pend.length ? 'outline' : 'primary'} icon={<FolderOpen className="h-3.5 w-3.5" />} onClick={() => setAskFolder((x) => !x)}>Indicar a pasta dos arquivos</Button>
          </>
        )}
      </div>
      {askFolder && !busy && (
        <div className="flex flex-wrap items-center gap-2 pl-7">
          <Input className="min-w-[320px] flex-1" value={folder} onChange={(e) => setFolder(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && folder.trim() && run([folder.trim()])}
            placeholder="Pasta com os TXT do SPED Fiscal e da EFD-Contribuições (ex.: C:\SPED)" icon={<FolderOpen className="h-4 w-4" />} />
          {meta.native && <Button size="sm" onClick={pick}>Procurar…</Button>}
          <Button size="sm" variant="primary" icon={<Search className="h-3.5 w-3.5" />} disabled={!folder.trim()} onClick={() => run([folder.trim()])}>Procurar e indexar</Button>
          <span className="w-full text-[12px] text-muted">Os arquivos são reconhecidos pelo conteúdo (mesmo hash da importação), então podem ter sido renomeados ou estar em subpastas.
            Não é preciso reimportar; importar de novo os mesmos arquivos pela tela Arquivos também guarda as linhas.</span>
        </div>
      )}
    </div>
  )
}
