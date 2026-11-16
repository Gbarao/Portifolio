import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { api } from './lib/api'
import { AppProvider } from './lib/store'
import type { Meta, UiState } from './lib/types'

function Boot() {
  const [boot, setBoot] = useState<{ meta: Meta; state: Partial<UiState> } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    Promise.all([api.get<Meta>('/api/meta'), api.get<Partial<UiState>>('/api/state')])
      .then(([meta, state]) => setBoot({ meta, state }))
      .catch((e) => setErr(String(e.message || e)))
  }, [])
  if (err) return <div className="flex h-full items-center justify-center p-8 text-center text-[14px] text-bad">Não foi possível conectar ao motor local: {err}</div>
  if (!boot) return (
    <div className="flex h-full items-center justify-center">
      <div className="flex items-center gap-3 text-[13px] text-muted">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />Abrindo base local…
      </div>
    </div>
  )
  return <AppProvider meta={boot.meta} initial={boot.state}><App /></AppProvider>
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><Boot /></React.StrictMode>)
