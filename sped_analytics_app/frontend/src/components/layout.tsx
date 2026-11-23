import { ChevronDown, ChevronsLeft, ChevronsRight, Maximize2, Minimize2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Button, Tip, cx } from './ui'

// ------------------------------------------------------------------ preferências locais (por computador)
function read<T>(key: string, def: T): T {
  try {
    const v = localStorage.getItem(`ui:${key}`)
    return v == null ? def : (JSON.parse(v) as T)
  } catch { return def }
}
function write(key: string, v: unknown) {
  try { localStorage.setItem(`ui:${key}`, JSON.stringify(v)) } catch { /* armazenamento indisponível */ }
}

export function useLocal<T>(key: string, def: T | (() => T)) {
  const [v, setV] = useState<T>(() => read(key, typeof def === 'function' ? (def as () => T)() : def))
  const set = useCallback((x: T | ((p: T) => T)) => {
    setV((p) => { const n = typeof x === 'function' ? (x as (p: T) => T)(p) : x; write(key, n); return n })
  }, [key])
  return [v, set] as const
}

/** Tela "baixa" (notebook): usada para começar com seções recolhidas. */
export const isShortScreen = () => typeof window !== 'undefined' && window.innerHeight < 820

// ------------------------------------------------------------------ painel lateral redimensionável e recolhível
export function SidePanel({ id, defaultWidth = 280, min = 200, max = 640, title, children, className }:
  { id: string; defaultWidth?: number; min?: number; max?: number; title: string; children: ReactNode; className?: string }) {
  const [w, setW] = useLocal(`side:${id}:w`, defaultWidth)
  const [open, setOpen] = useLocal(`side:${id}:open`, true)
  const drag = useRef<{ x: number; w: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!drag.current) return
      setW(Math.max(min, Math.min(max, drag.current.w + e.clientX - drag.current.x)))
    }
    const up = () => { if (drag.current) { drag.current = null; setDragging(false); document.body.style.cursor = ''; document.body.style.userSelect = '' } }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [min, max, setW])

  if (!open) {
    return (
      <Tip content={`Mostrar ${title.toLowerCase()}`} side="right">
        <button onClick={() => setOpen(true)} aria-label={`Mostrar ${title}`}
          className="flex w-8 shrink-0 flex-col items-center gap-2 rounded-xl border bg-panel py-3 text-muted shadow-card hover:bg-sunken hover:text-fg">
          <ChevronsRight className="h-4 w-4" />
          <span className="text-[11.5px] font-medium [writing-mode:vertical-rl]">{title}</span>
        </button>
      </Tip>
    )
  }
  return (
    <div className={cx('group/side relative flex shrink-0 flex-col', className)} style={{ width: w }}>
      {children}
      <div onMouseDown={(e) => { drag.current = { x: e.clientX, w }; setDragging(true); document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none' }}
        onDoubleClick={() => setW(defaultWidth)} title="Arraste para ajustar a largura · duplo clique volta ao padrão"
        className="group absolute -right-[7px] top-0 z-10 flex h-full w-[10px] cursor-col-resize justify-center">
        <div className={cx('h-full w-[3px] rounded-full transition-colors', dragging ? 'bg-accent' : 'group-hover:bg-accent/50')} />
      </div>
      <Tip content={`Recolher ${title.toLowerCase()}`}>
        <button onClick={() => setOpen(false)} aria-label={`Recolher ${title}`}
          className="absolute -right-3 top-3 z-20 flex h-6 w-6 items-center justify-center rounded-full border bg-panel text-muted opacity-0 shadow-card transition-opacity hover:text-fg focus:opacity-100 group-hover/side:opacity-100">
          <ChevronsLeft className="h-3.5 w-3.5" />
        </button>
      </Tip>
    </div>
  )
}

// ------------------------------------------------------------------ tela cheia para um painel (Esc para sair)
export function useMaximize() {
  const [on, setOn] = useState(false)
  useEffect(() => {
    if (!on) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape' && !document.querySelector('[data-radix-popper-content-wrapper],[role="dialog"]')) setOn(false) }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [on])
  const toggle = useCallback(() => setOn((x) => !x), [])
  return { on, toggle, cls: on ? '!fixed inset-2 z-40 !m-0 shadow-pop' : '' }
}

export function MaxButton({ on, onClick, size = 'icon' }: { on: boolean; onClick: () => void; size?: 'icon' | 'icon-sm' }) {
  return (
    <Tip content={on ? 'Sair da tela cheia (Esc)' : 'Tela cheia'}>
      <Button size={size} variant="ghost" aria-label={on ? 'Sair da tela cheia' : 'Tela cheia'} onClick={onClick}>
        {on ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </Button>
    </Tip>
  )
}

/** Fundo escurecido atrás de um painel em tela cheia. */
export function MaxBackdrop({ on, onClose }: { on: boolean; onClose: () => void }) {
  if (!on) return null
  return <div className="fixed inset-0 z-30 bg-black/30 backdrop-blur-[1px]" onClick={onClose} />
}

// ------------------------------------------------------------------ seção recolhível (configurações, indicadores)
export function useCollapsed(id: string, defShort = true) {
  return useLocal<boolean>(`collapse:${id}`, () => (defShort ? isShortScreen() : false))
}

export function CollapseToggle({ collapsed, onToggle, label }: { collapsed: boolean; onToggle: () => void; label: string }) {
  return (
    <button onClick={onToggle} aria-expanded={!collapsed}
      className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[12px] font-medium text-muted hover:bg-sunken hover:text-fg">
      <ChevronDown className={cx('h-3.5 w-3.5 transition-transform', collapsed && '-rotate-90')} />
      {collapsed ? `Mostrar ${label}` : `Recolher ${label}`}
    </button>
  )
}

// ------------------------------------------------------------------ divisor vertical arrastável (altura de um painel inferior)
export function useDragHeight(id: string, def: number, min = 140, maxFrac = 0.85) {
  const [h, setH] = useLocal(`height:${id}`, def)
  const ref = useRef<{ y: number; h: number } | null>(null)
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!ref.current) return
      setH(Math.max(min, Math.min(window.innerHeight * maxFrac, ref.current.h - (e.clientY - ref.current.y))))
    }
    const up = () => { if (ref.current) { ref.current = null; document.body.style.cursor = ''; document.body.style.userSelect = '' } }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [min, maxFrac, setH])
  const handle = (
    <div className="group flex h-3 shrink-0 cursor-row-resize items-center justify-center" title="Arraste para ajustar a altura · duplo clique volta ao padrão"
      onMouseDown={(e) => { ref.current = { y: e.clientY, h }; document.body.style.cursor = 'row-resize'; document.body.style.userSelect = 'none' }}
      onDoubleClick={() => setH(def)}>
      <div className="h-1 w-12 rounded-full bg-line transition-colors group-hover:bg-accent/60" />
    </div>
  )
  return { h, setH, handle }
}
