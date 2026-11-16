import * as RDialog from '@radix-ui/react-dialog'
import * as RMenu from '@radix-ui/react-dropdown-menu'
import * as RPopover from '@radix-ui/react-popover'
import * as RTooltip from '@radix-ui/react-tooltip'
import clsx from 'clsx'
import { Check, ChevronDown, Loader2, X } from 'lucide-react'
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'

export const cx = clsx

// ------------------------------------------------------------------ Botões
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'sm' | 'md' | 'icon' | 'icon-sm'
const variants: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent/90 shadow-sm',
  secondary: 'bg-sunken text-fg hover:bg-line/70',
  outline: 'border bg-panel text-fg hover:bg-sunken',
  ghost: 'text-fg/80 hover:bg-sunken hover:text-fg',
  danger: 'bg-bad text-white hover:bg-bad/90',
}
const sizes: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-[12.5px] gap-1.5 rounded-md',
  md: 'h-8.5 h-[34px] px-3 text-[13px] gap-2 rounded-lg',
  icon: 'h-[34px] w-[34px] rounded-lg justify-center',
  'icon-sm': 'h-7 w-7 rounded-md justify-center',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'outline', size = 'md', loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button ref={ref} disabled={disabled || loading}
      className={cx('inline-flex shrink-0 items-center font-medium transition-colors focus-ring select-none',
        'disabled:pointer-events-none disabled:opacity-50', variants[variant], sizes[size], className)} {...rest}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  )
})

// ------------------------------------------------------------------ Entradas
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { icon?: ReactNode }>(
  function Input({ className, icon, ...rest }, ref) {
    return (
      <div className={cx('relative flex items-center', className)}>
        {icon && <span className="pointer-events-none absolute left-2.5 text-muted">{icon}</span>}
        <input ref={ref} {...rest}
          className={cx('h-[34px] w-full rounded-lg border bg-panel px-3 text-[13px] placeholder:text-muted/70 focus-ring',
            'transition-colors hover:border-muted/40', icon && 'pl-8')} />
      </div>
    )
  })

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cx('relative inline-flex', className)}>
      <select {...rest}
        className="h-[34px] w-full appearance-none rounded-lg border bg-panel pl-2.5 pr-8 text-[13px] text-fg focus-ring hover:border-muted/40">
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
    </div>
  )
}

export function Checkbox({ checked, onChange, className }: { checked: boolean; onChange?: (v: boolean) => void; className?: string }) {
  return (
    <button type="button" role="checkbox" aria-checked={checked} onClick={(e) => { e.stopPropagation(); onChange?.(!checked) }}
      className={cx('flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors focus-ring',
        checked ? 'border-accent bg-accent text-accent-fg' : 'bg-panel hover:border-muted', className)}>
      {checked && <Check className="h-3 w-3" strokeWidth={3} />}
    </button>
  )
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-[13px]">
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cx('relative h-5 w-9 rounded-full transition-colors focus-ring', checked ? 'bg-accent' : 'bg-line')}>
        <span className={cx('absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-0.5')} />
      </button>
      {label}
    </label>
  )
}

export function Segmented<T extends string>({ value, onChange, options }:
  { value: T; onChange: (v: T) => void; options: { value: T; label: string; icon?: ReactNode }[] }) {
  return (
    <div className="inline-flex h-[34px] items-center rounded-lg bg-sunken p-0.5">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={cx('inline-flex h-full items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-all focus-ring',
            value === o.value ? 'bg-panel text-fg shadow-sm' : 'text-muted hover:text-fg')}>
          {o.icon}{o.label}
        </button>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ Superfícies
export function Card({ className, children, ...rest }: { className?: string; children?: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('rounded-xl border bg-panel shadow-card', className)} {...rest}>{children}</div>
}

export function CardHeader({ title, subtitle, actions, icon }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 border-b px-4 py-3">
      {icon && <div className="mt-0.5 text-muted">{icon}</div>}
      <div className="min-w-0 flex-1">
        <div className="text-[14px] font-semibold">{title}</div>
        {subtitle && <div className="mt-0.5 text-[12.5px] text-muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

const tones = {
  neutral: 'bg-sunken text-fg/80',
  accent: 'bg-accent/12 text-accent bg-accent/10',
  ok: 'bg-ok/12 text-ok bg-ok/10',
  warn: 'bg-warn/15 text-warn',
  bad: 'bg-bad/10 text-bad',
  info: 'bg-info/10 text-info',
}
export type Tone = keyof typeof tones
export function Badge({ tone = 'neutral', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cx('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] font-medium', tones[tone], className)}>{children}</span>
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx('h-4 w-4 animate-spin text-muted', className)} />
}

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cx('h-1.5 w-full overflow-hidden rounded-full bg-sunken', className)}>
      <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }} />
    </div>
  )
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-2 p-6 text-center">
      {icon && <div className="rounded-full bg-sunken p-3 text-muted">{icon}</div>}
      <div className="text-[14px] font-medium">{title}</div>
      {children && <div className="max-w-md text-[12.5px] text-muted">{children}</div>}
    </div>
  )
}

export function Kpi({ label, value, icon, hint, loading, tone }: { label: string; value: ReactNode; icon?: ReactNode; hint?: ReactNode; loading?: boolean; tone?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-xl border bg-panel px-3.5 py-2.5 shadow-card">
      <div className="flex items-center gap-1.5 text-[11.5px] font-medium uppercase tracking-wide text-muted">
        {icon && <span className={cx('opacity-80', tone)}>{icon}</span>}{label}
      </div>
      {loading ? <div className="skeleton h-5 w-28" /> : <div className="num truncate text-[17px] font-semibold tracking-tight">{value}</div>}
      {hint && <div className="truncate text-[11.5px] text-muted">{hint}</div>}
    </div>
  )
}

// ------------------------------------------------------------------ Sobreposições
export function Popover({ trigger, children, align = 'start', className, open, onOpenChange }:
  { trigger: ReactNode; children: ReactNode; align?: 'start' | 'center' | 'end'; className?: string; open?: boolean; onOpenChange?: (o: boolean) => void }) {
  return (
    <RPopover.Root open={open} onOpenChange={onOpenChange}>
      <RPopover.Trigger asChild>{trigger}</RPopover.Trigger>
      <RPopover.Portal>
        <RPopover.Content align={align} sideOffset={6} collisionPadding={12}
          className={cx('z-50 rounded-xl border bg-panel shadow-pop outline-none animate-in', className)}>
          {children}
        </RPopover.Content>
      </RPopover.Portal>
    </RPopover.Root>
  )
}

export function Dialog({ open, onOpenChange, title, description, children, footer, wide, full }:
  { open: boolean; onOpenChange: (o: boolean) => void; title: ReactNode; description?: ReactNode; children?: ReactNode; footer?: ReactNode; wide?: boolean; full?: boolean }) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]" />
        <RDialog.Content
          className={cx('fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border bg-panel shadow-pop outline-none animate-in',
            full ? 'h-[90vh] w-[94vw]' : wide ? 'w-[760px] max-w-[94vw]' : 'w-[480px] max-w-[94vw]')}>
          <div className="flex items-start gap-3 border-b px-5 py-4">
            <div className="flex-1">
              <RDialog.Title className="text-[15px] font-semibold">{title}</RDialog.Title>
              {description && <RDialog.Description className="mt-1 text-[12.5px] text-muted">{description}</RDialog.Description>}
            </div>
            <RDialog.Close asChild><Button variant="ghost" size="icon-sm" aria-label="Fechar"><X className="h-4 w-4" /></Button></RDialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-5 py-4">{children}</div>
          {footer && <div className="flex justify-end gap-2 border-t px-5 py-3">{footer}</div>}
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  )
}

export function Menu({ trigger, children, align = 'end' }: { trigger: ReactNode; children: ReactNode; align?: 'start' | 'end' }) {
  return (
    <RMenu.Root>
      <RMenu.Trigger asChild>{trigger}</RMenu.Trigger>
      <RMenu.Portal>
        <RMenu.Content align={align} sideOffset={6} className="z-50 min-w-[220px] rounded-xl border bg-panel p-1 shadow-pop animate-in">
          {children}
        </RMenu.Content>
      </RMenu.Portal>
    </RMenu.Root>
  )
}
export function MenuItem({ icon, children, onSelect, hint, danger }: { icon?: ReactNode; children: ReactNode; onSelect?: () => void; hint?: string; danger?: boolean }) {
  return (
    <RMenu.Item onSelect={onSelect}
      className={cx('flex cursor-pointer select-none items-start gap-2.5 rounded-lg px-2.5 py-2 text-[13px] outline-none data-[highlighted]:bg-sunken',
        danger && 'text-bad')}>
      {icon && <span className="mt-0.5 text-muted">{icon}</span>}
      <span className="flex-1"><span className="block">{children}</span>{hint && <span className="block text-[11.5px] text-muted">{hint}</span>}</span>
    </RMenu.Item>
  )
}
export const MenuSep = () => <RMenu.Separator className="my-1 h-px bg-line" />
export const MenuLabel = ({ children }: { children: ReactNode }) => <RMenu.Label className="px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{children}</RMenu.Label>

export function Tip({ content, children, side = 'top' }: { content: ReactNode; children: ReactNode; side?: 'top' | 'bottom' | 'left' | 'right' }) {
  if (!content) return <>{children}</>
  return (
    <RTooltip.Root delayDuration={300}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content side={side} sideOffset={6} className="z-[60] max-w-xs rounded-md bg-fg px-2 py-1 text-[12px] text-bg shadow-pop">
          {content}
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  )
}
export const TipProvider = RTooltip.Provider

export function Confirm({ open, onOpenChange, title, children, confirmLabel = 'Confirmar', danger, onConfirm, loading }:
  { open: boolean; onOpenChange: (o: boolean) => void; title: string; children?: ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => void; loading?: boolean }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={title}
      footer={<>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
        <Button variant={danger ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
      </>}>
      <div className="text-[13px] text-fg/80">{children}</div>
    </Dialog>
  )
}

export function Field({ label, children, hint, className }: { label: string; children: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <label className={cx('flex flex-col gap-1.5', className)}>
      <span className="text-[12px] font-medium text-muted">{label}</span>
      {children}
      {hint && <span className="text-[11.5px] text-muted">{hint}</span>}
    </label>
  )
}
