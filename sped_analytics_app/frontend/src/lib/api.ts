import type { Job } from './types'

export class ApiError extends Error {}

async function handle(r: Response) {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try { const j = await r.json(); msg = j.detail || msg } catch { /* sem corpo */ }
    throw new ApiError(msg)
  }
  return r.json()
}

export const api = {
  get: <T = any>(url: string, signal?: AbortSignal): Promise<T> => fetch(url, { signal }).then(handle),
  post: <T = any>(url: string, body?: any, signal?: AbortSignal): Promise<T> =>
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}), signal }).then(handle),
  put: <T = any>(url: string, body?: any): Promise<T> =>
    fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) }).then(handle),
  del: <T = any>(url: string): Promise<T> => fetch(url, { method: 'DELETE' }).then(handle),
  upload: <T = any>(url: string, files: File[], onProgress?: (f: number) => void): Promise<T> =>
    new Promise((resolve, reject) => {
      const fd = new FormData()
      files.forEach((f) => fd.append('files', f, f.name))
      const xhr = new XMLHttpRequest()
      xhr.open('POST', url)
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
      xhr.onload = () => (xhr.status < 300 ? resolve(JSON.parse(xhr.responseText)) : reject(new ApiError(xhr.responseText)))
      xhr.onerror = () => reject(new ApiError('Falha no envio'))
      xhr.send(fd)
    }),
}

/** Acompanha uma tarefa em segundo plano até terminar. */
export async function waitJob(id: string, onUpdate?: (j: Job) => void): Promise<Job> {
  for (;;) {
    const j = await api.get<Job>(`/api/jobs/${id}`)
    onUpdate?.(j)
    if (j.status !== 'running') return j
    await new Promise((r) => setTimeout(r, 400))
  }
}

/** Baixa um arquivo gerado no servidor (exportações, backups). */
export function download(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}
