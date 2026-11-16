import { BarChart3, ChevronsLeft, Layers3, ChevronsRight, FolderInput, Lock, Monitor, Moon, ShieldCheck, Sun, Wand2, Zap } from 'lucide-react'
import { useState } from 'react'
import { Toaster } from 'sonner'
import { cx, Menu, MenuItem, Tip, TipProvider } from './components/ui'
import { useApp, useTheme } from './lib/store'
import type { Page } from './lib/types'
import { AnalysisPage } from './pages/AnalysisPage'
import { AuditPage } from './pages/AuditPage'
import { FilesPage } from './pages/FilesPage'
import { RulesPage } from './pages/RulesPage'

const PAGES: { key: Page; label: string; icon: any; title: string; subtitle: string }[] = [
  { key: 'analise', label: 'Análise', icon: BarChart3, title: 'Análise consolidada de entradas', subtitle: 'SPED Fiscal × EFD-Contribuições por empresa, fornecedor, CFOP e item' },
  { key: 'arquivos', label: 'Arquivos', icon: FolderInput, title: 'Central de arquivos', subtitle: 'Importação, cobertura fiscal, gestão da base e backup' },
  { key: 'regras', label: 'Regras e filtros', icon: Wand2, title: 'Regras e biblioteca', subtitle: 'Filtros sob demanda, filtros salvos e análises congeladas' },
  { key: 'auditoria', label: 'Auditoria', icon: ShieldCheck, title: 'Auditoria de divergências', subtitle: 'Fechamento, qualidade do cruzamento e inconsistências' },
]

export default function App() {
  const { state, set, filters, applyPreset, meta } = useApp()
  const [theme, setTheme] = useTheme()
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem('sidebar') === '1' } catch { return false } })
  const toggleSidebar = () => { setCollapsed((c) => { try { localStorage.setItem('sidebar', c ? '0' : '1') } catch { /* */ } return !c }) }
  const page = PAGES.find((p) => p.key === state.page) ?? PAGES[0]
  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor

  return (
    <TipProvider>
      <div className="flex h-full">
        {/* barra lateral */}
        <aside className={cx('flex shrink-0 flex-col border-r bg-panel transition-[width] duration-200', collapsed ? 'w-[60px]' : 'w-[236px]')}>
          <div className="flex h-14 items-center gap-2.5 px-3.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-fg shadow-sm">
              <Layers3 className="h-[18px] w-[18px]" />
            </div>
            {!collapsed && <div className="min-w-0 leading-tight"><div className="truncate text-[13.5px] font-semibold">Consolidação Fiscal</div><div className="truncate text-[11.5px] text-muted">SPED · EFD-Contribuições</div></div>}
          </div>
          <nav className="space-y-0.5 px-2 pt-2">
            {PAGES.map((p) => {
              const Icon = p.icon
              const active = state.page === p.key
              return (
                <Tip key={p.key} content={collapsed ? p.label : null} side="right">
                  <button onClick={() => set({ page: p.key })}
                    className={cx('flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-colors focus-ring',
                      active ? 'bg-accent/10 text-accent' : 'text-fg/75 hover:bg-sunken hover:text-fg')}>
                    <Icon className="h-[18px] w-[18px] shrink-0" />{!collapsed && <span className="truncate">{p.label}</span>}
                  </button>
                </Tip>
              )
            })}
          </nav>

          {!collapsed && (
            <div className="mt-5 min-h-0 flex-1 overflow-auto px-2">
              <div className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Filtros salvos</div>
              {filters.length === 0 && <div className="px-2.5 text-[12px] text-muted">Salve filtros em “Regras e filtros”.</div>}
              {filters.slice(0, 30).map((f) => (
                <button key={f.id} onClick={() => applyPreset(f)} title={f.categoria}
                  className={cx('flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-left text-[12.5px] hover:bg-sunken',
                    state.appliedFilterName === f.nome ? 'text-accent' : 'text-fg/80')}>
                  <Zap className="h-3.5 w-3.5 shrink-0 opacity-70" /><span className="truncate">{f.nome}</span>
                </button>
              ))}
            </div>
          )}
          {collapsed && <div className="flex-1" />}

          <div className="space-y-1 border-t p-2">
            <Menu align="start" trigger={
              <button className="flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] text-fg/75 hover:bg-sunken">
                <ThemeIcon className="h-[18px] w-[18px] shrink-0" />{!collapsed && <span>Tema: {theme === 'dark' ? 'escuro' : theme === 'light' ? 'claro' : 'sistema'}</span>}
              </button>}>
              <MenuItem icon={<Sun className="h-4 w-4" />} onSelect={() => setTheme('light')}>Claro</MenuItem>
              <MenuItem icon={<Moon className="h-4 w-4" />} onSelect={() => setTheme('dark')}>Escuro</MenuItem>
              <MenuItem icon={<Monitor className="h-4 w-4" />} onSelect={() => setTheme('system')}>Seguir o sistema</MenuItem>
            </Menu>
            <button onClick={toggleSidebar} className="flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] text-fg/75 hover:bg-sunken">
              {collapsed ? <ChevronsRight className="h-[18px] w-[18px]" /> : <><ChevronsLeft className="h-[18px] w-[18px]" /><span>Recolher menu</span></>}
            </button>
            {!collapsed && (
              <Tip content="Os dados ficam apenas no seu computador; a interface roda em 127.0.0.1." side="right">
                <div className="flex items-center gap-2 px-2.5 pt-1 text-[11.5px] text-muted"><Lock className="h-3.5 w-3.5" />100% local · v{meta.version}</div>
              </Tip>
            )}
          </div>
        </aside>

        {/* conteúdo */}
        <main className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-panel/80 px-5 backdrop-blur">
            <div className="min-w-0">
              <h1 className="truncate text-[15px] font-semibold tracking-tight">{page.title}</h1>
              <p className="truncate text-[12px] text-muted">{page.subtitle}</p>
            </div>
          </header>
          <div className={cx('min-h-0 flex-1', state.page === 'analise' || state.page === 'auditoria' ? 'overflow-hidden' : 'overflow-auto')}>
            {state.page === 'analise' && <AnalysisPage />}
            {state.page === 'arquivos' && <FilesPage />}
            {state.page === 'regras' && <RulesPage />}
            {state.page === 'auditoria' && <AuditPage />}
          </div>
        </main>
      </div>
      <Toaster position="bottom-right" richColors closeButton theme={theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light'}
        toastOptions={{ style: { fontFamily: 'inherit', fontSize: 13 } }} />
    </TipProvider>
  )
}
