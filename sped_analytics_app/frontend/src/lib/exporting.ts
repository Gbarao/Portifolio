import { toast } from 'sonner'
import { api, download } from './api'
import { fmtInt } from './format'

/** Gera uma exportação no servidor, avisa o usuário e baixa o arquivo. */
export function runExport(url: string, body: any, label: string) {
  const id = toast.loading(`Gerando ${label}…`)
  return api.post(url, body)
    .then((r) => {
      toast.success(`${label} pronto${r.linhas != null ? ` — ${fmtInt(r.linhas)} linhas` : ''}`, {
        id, description: r.path, duration: 9000,
        action: { label: 'Abrir pasta', onClick: () => api.post('/api/open-folder', { path: r.path }) },
      })
      download(r.url)
    })
    .catch((e) => toast.error(e.message, { id }))
}
