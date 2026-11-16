import { useVirtualizer } from '@tanstack/react-virtual'
import { Building2, CalendarRange, ChevronDown, FilterX, Hash, Layers, MapPin, Package, Plus, Search, SlidersHorizontal, Truck, X } from 'lucide-react'
import { useMemo, useRef, useState, type ReactNode } from 'react'
import { fmtCnpj, fmtComp } from '../lib/format'
import { useApp } from '../lib/store'
import type { GlobalFilters, Opt } from '../lib/types'
import { Button, Checkbox, cx, Input, Popover, Select } from './ui'

function norm(s: string) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

function MultiList({ options, value, onChange, format }: { options: Opt[]; value: string[]; onChange: (v: string[]) => void; format?: (v: string) => string }) {
  const [q, setQ] = useState('')
  const sel = useMemo(() => new Set(value), [value])
  const list = useMemo(() => {
    const n = norm(q.trim())
    const base = n ? options.filter(([v, l]) => norm(`${v} ${format ? format(v) : ''} ${l ?? ''}`).includes(n)) : options
    // selecionados primeiro
    return [...base.filter(([v]) => sel.has(v)), ...base.filter(([v]) => !sel.has(v))]
  }, [options, q, sel, format])
  const ref = useRef<HTMLDivElement>(null)
  const virt = useVirtualizer({ count: list.length, getScrollElement: () => ref.current, estimateSize: () => 40, overscan: 10 })
  return (
    <div className="flex w-[380px] flex-col">
      <div className="border-b p-2">
        <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por código ou nome…" icon={<Search className="h-4 w-4" />} />
      </div>
      <div ref={ref} className="h-[300px] overflow-auto p-1">
        {list.length === 0 && <div className="p-6 text-center text-[12.5px] text-muted">Nada encontrado</div>}
        <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
          {virt.getVirtualItems().map((vi) => {
            const [v, l] = list[vi.index]
            const on = sel.has(v)
            const code = format ? format(v) : v
            return (
              <div key={v} style={{ transform: `translateY(${vi.start}px)`, height: 40 }}
                className={cx('absolute inset-x-0 flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 hover:bg-sunken', on && 'bg-accent/[0.06]')}
                onClick={() => onChange(on ? value.filter((x) => x !== v) : [...value, v])}>
                <Checkbox checked={on} onChange={() => onChange(on ? value.filter((x) => x !== v) : [...value, v])} />
                <div className="min-w-0 flex-1 leading-tight">
                  <div className="truncate text-[13px]">{l && l !== v ? l : code}</div>
                  {l && l !== v && <div className="num truncate font-mono text-[11px] text-muted">{code}</div>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <div className="flex items-center justify-between border-t px-3 py-2 text-[12px] text-muted">
        <span>{value.length ? `${value.length} selecionado(s)` : `${options.length.toLocaleString('pt-BR')} opções`}</span>
        <div className="flex gap-1">
          {q && list.length > 0 && list.length <= 500 && (
            <Button size="sm" variant="ghost" onClick={() => onChange(Array.from(new Set([...value, ...list.map(([v]) => v)])))}>Marcar visíveis</Button>
          )}
          {value.length > 0 && <Button size="sm" variant="ghost" onClick={() => onChange([])}>Limpar</Button>}
        </div>
      </div>
    </div>
  )
}

function FilterButton({ icon, label, count, children, summary }: { icon: ReactNode; label: string; count: number; children: ReactNode; summary?: string }) {
  return (
    <Popover trigger={
      <button className={cx('inline-flex h-[34px] items-center gap-1.5 rounded-lg border px-2.5 text-[13px] transition-colors focus-ring',
        count ? 'border-accent/40 bg-accent/[0.07] text-fg' : 'bg-panel text-fg/80 hover:bg-sunken')}>
        <span className={count ? 'text-accent' : 'text-muted'}>{icon}</span>
        <span className="font-medium">{label}</span>
        {count > 0 && <span className="max-w-[160px] truncate text-muted">{summary ?? count}</span>}
        <ChevronDown className="h-3.5 w-3.5 text-muted" />
      </button>
    }>{children}</Popover>
  )
}

export function FilterBar() {
  const { state, set, options } = useApp()
  const gf = state.gf
  const upd = (patch: Partial<GlobalFilters>) => set((s) => {
    const n: any = { ...s.gf, ...patch }
    Object.keys(n).forEach((k) => { if (n[k] == null || n[k] === '' || (Array.isArray(n[k]) && !n[k].length)) delete n[k] })
    return { gf: n }
  })
  const comps = options?.competencias ?? []
  const label = (list: Opt[] | undefined, v: string) => list?.find((o) => o[0] === v)?.[1] || v

  const periodo = gf.competencias?.length ? `${gf.competencias.length} mês(es)`
    : gf.comp_ini || gf.comp_fim ? `${gf.comp_ini ? fmtComp(gf.comp_ini) : '…'} – ${gf.comp_fim ? fmtComp(gf.comp_fim) : '…'}` : undefined
  const textCount = ['raizes_fornecedor', 'busca_fornecedor', 'cfop_prefixo', 'busca_item', 'ncm_prefixo'].filter((k) => (gf as any)[k]?.length).length
  const any = Object.keys(gf).length > 0

  const sum1 = (arr: string[] | undefined, list: Opt[] | undefined, fmt?: (v: string) => string) =>
    !arr?.length ? undefined : arr.length === 1 ? (label(list, arr[0]) !== arr[0] ? label(list, arr[0]) : fmt ? fmt(arr[0]) : arr[0]) : `${arr.length} selecionados`

  return (
    <div className="flex flex-wrap items-center gap-2">
      <FilterButton icon={<CalendarRange className="h-4 w-4" />} label="Período" count={periodo ? 1 : 0} summary={periodo}>
        <div className="w-[340px] space-y-3 p-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1 text-[12px] text-muted">De
              <Select className="w-full" value={gf.comp_ini || ''} onChange={(e) => upd({ comp_ini: e.target.value || undefined, competencias: [] })}>
                <option value="">Início</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
              </Select>
            </label>
            <label className="space-y-1 text-[12px] text-muted">Até
              <Select className="w-full" value={gf.comp_fim || ''} onChange={(e) => upd({ comp_fim: e.target.value || undefined, competencias: [] })}>
                <option value="">Fim</option>{comps.map((c) => <option key={c} value={c}>{fmtComp(c)}</option>)}
              </Select>
            </label>
          </div>
          <div>
            <div className="mb-1.5 text-[12px] text-muted">Ou meses específicos</div>
            <div className="flex max-h-[180px] flex-wrap gap-1 overflow-auto">
              {comps.map((c) => {
                const on = gf.competencias?.includes(c)
                return (
                  <button key={c} onClick={() => upd({ competencias: on ? gf.competencias!.filter((x) => x !== c) : [...(gf.competencias || []), c], comp_ini: undefined, comp_fim: undefined })}
                    className={cx('rounded-md border px-2 py-1 text-[12px] transition-colors', on ? 'border-accent bg-accent text-accent-fg' : 'hover:bg-sunken')}>
                    {fmtComp(c)}
                  </button>
                )
              })}
              {!comps.length && <span className="text-[12px] text-muted">Nenhuma competência importada</span>}
            </div>
          </div>
          {periodo && <Button size="sm" variant="ghost" onClick={() => upd({ comp_ini: undefined, comp_fim: undefined, competencias: [] })}>Limpar período</Button>}
        </div>
      </FilterButton>

      <FilterButton icon={<Building2 className="h-4 w-4" />} label="Filial" count={gf.filiais?.length ?? 0} summary={sum1(gf.filiais, options?.filial, fmtCnpj)}>
        <MultiList options={options?.filial ?? []} value={gf.filiais ?? []} onChange={(v) => upd({ filiais: v })} format={fmtCnpj} />
      </FilterButton>
      <FilterButton icon={<Truck className="h-4 w-4" />} label="Fornecedor" count={gf.fornecedores?.length ?? 0} summary={sum1(gf.fornecedores, options?.fornecedor, fmtCnpj)}>
        <MultiList options={options?.fornecedor ?? []} value={gf.fornecedores ?? []} onChange={(v) => upd({ fornecedores: v })} format={fmtCnpj} />
      </FilterButton>
      <FilterButton icon={<Hash className="h-4 w-4" />} label="CFOP" count={gf.cfops?.length ?? 0} summary={gf.cfops?.join(', ')}>
        <MultiList options={options?.cfop ?? []} value={gf.cfops ?? []} onChange={(v) => upd({ cfops: v })} />
      </FilterButton>
      <FilterButton icon={<Package className="h-4 w-4" />} label="Item" count={gf.itens?.length ?? 0} summary={sum1(gf.itens, options?.item)}>
        <MultiList options={options?.item ?? []} value={gf.itens ?? []} onChange={(v) => upd({ itens: v })} />
      </FilterButton>
      <FilterButton icon={<MapPin className="h-4 w-4" />} label="UF" count={gf.ufs_filial?.length ?? 0} summary={gf.ufs_filial?.join(', ')}>
        <MultiList options={options?.uf ?? []} value={gf.ufs_filial ?? []} onChange={(v) => upd({ ufs_filial: v })} />
      </FilterButton>

      <FilterButton icon={<SlidersHorizontal className="h-4 w-4" />} label="Mais" count={textCount} summary={textCount ? `${textCount}` : undefined}>
        <MoreFilters gf={gf} upd={upd} />
      </FilterButton>

      {any && (
        <Button variant="ghost" size="sm" icon={<FilterX className="h-4 w-4" />} onClick={() => set({ gf: {} })} className="text-muted">
          Limpar filtros
        </Button>
      )}
    </div>
  )
}

function MoreFilters({ gf, upd }: { gf: GlobalFilters; upd: (p: Partial<GlobalFilters>) => void }) {
  const [v, setV] = useState({
    raizes: (gf.raizes_fornecedor || []).join('; '), forn: gf.busca_fornecedor || '', cfop: gf.cfop_prefixo || '',
    item: gf.busca_item || '', ncm: gf.ncm_prefixo || '',
  })
  const apply = () => upd({
    raizes_fornecedor: v.raizes.split(/[;,\s]+/).map((x) => x.replace(/\D/g, '')).filter(Boolean),
    busca_fornecedor: v.forn.trim() || undefined, cfop_prefixo: v.cfop.trim() || undefined,
    busca_item: v.item.trim() || undefined, ncm_prefixo: v.ncm.trim() || undefined,
  })
  const f = (k: keyof typeof v, label: string, ph: string) => (
    <label className="space-y-1 text-[12px] text-muted">
      {label}
      <Input value={v[k]} placeholder={ph} onChange={(e) => setV({ ...v, [k]: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && apply()} />
    </label>
  )
  return (
    <div className="w-[360px] space-y-2.5 p-3">
      {f('forn', 'Razão social do fornecedor contém', 'ex.: distribuidora')}
      {f('raizes', 'Raiz de CNPJ do fornecedor (8 dígitos)', 'ex.: 12345678; 87654321')}
      {f('item', 'Descrição do item contém', 'ex.: malte')}
      <div className="grid grid-cols-2 gap-2">
        {f('cfop', 'CFOP começa com', 'ex.: 1.1 → 11')}
        {f('ncm', 'NCM começa com', 'ex.: 2203')}
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button size="sm" variant="ghost" onClick={() => { setV({ raizes: '', forn: '', cfop: '', item: '', ncm: '' }); upd({ raizes_fornecedor: [], busca_fornecedor: undefined, cfop_prefixo: undefined, busca_item: undefined, ncm_prefixo: undefined }) }}>Limpar</Button>
        <Button size="sm" variant="primary" onClick={apply}>Aplicar</Button>
      </div>
    </div>
  )
}

/** Editor da hierarquia (ordem dos níveis da árvore). */
export function HierarchyEditor() {
  const { state, set, meta, dimLabel } = useApp()
  const h = state.hierarchy
  const move = (i: number, d: number) => {
    const n = [...h]; const j = i + d
    if (j < 0 || j >= n.length) return
    ;[n[i], n[j]] = [n[j], n[i]]; set({ hierarchy: n })
  }
  const avail = meta.dimensions.filter((d) => !h.includes(d.key))
  return (
    <Popover align="start" trigger={
      <button className="inline-flex h-[34px] max-w-[460px] items-center gap-1.5 rounded-lg border bg-panel px-2.5 text-[13px] hover:bg-sunken focus-ring">
        <Layers className="h-4 w-4 text-muted" />
        <span className="truncate">{h.map(dimLabel).join('  ›  ')}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted" />
      </button>
    }>
      <div className="w-[320px] p-2">
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Níveis da hierarquia</div>
        {h.map((d, i) => (
          <div key={d} className="group flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-sunken">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-accent/10 text-[11px] font-semibold text-accent">{i + 1}</span>
            <span className="flex-1 text-[13px]">{dimLabel(d)}</span>
            <button className="rounded px-1 text-muted hover:text-fg disabled:opacity-30" disabled={i === 0} onClick={() => move(i, -1)}>↑</button>
            <button className="rounded px-1 text-muted hover:text-fg disabled:opacity-30" disabled={i === h.length - 1} onClick={() => move(i, 1)}>↓</button>
            <button className="rounded p-0.5 text-muted hover:text-bad disabled:opacity-30" disabled={h.length === 1} onClick={() => set({ hierarchy: h.filter((x) => x !== d) })}><X className="h-3.5 w-3.5" /></button>
          </div>
        ))}
        <div className="mt-2 border-t px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Adicionar nível</div>
        <div className="flex flex-wrap gap-1 px-1.5 pb-1">
          {avail.map((d) => (
            <button key={d.key} onClick={() => set({ hierarchy: [...h, d.key] })}
              className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[12px] hover:border-accent/50 hover:bg-accent/5">
              <Plus className="h-3 w-3" />{d.label}
            </button>
          ))}
        </div>
        <div className="mt-1 border-t px-2 pt-2">
          <Button size="sm" variant="ghost" onClick={() => set({ hierarchy: ['filial', 'fornecedor', 'cfop', 'item'] })}>Restaurar padrão</Button>
        </div>
      </div>
    </Popover>
  )
}

export function MetricsPicker() {
  const { state, set, meta } = useApp()
  const sel = new Set(state.metrics)
  const groups: [string, string[]][] = [
    ['Quantidades e valores', ['qtd', 'unid', 'preco_medio', 'vl_item', 'vl_desc', 'vl_contabil']],
    ['ICMS / ST / IPI', ['vl_bc_icms', 'vl_icms', 'vl_bc_icms_st', 'vl_icms_st_fcp', 'vl_bc_ipi', 'vl_ipi']],
    ['PIS / COFINS', ['cst_pis', 'vl_bc_pis', 'vl_pis', 'cst_cofins', 'vl_bc_cofins', 'vl_cofins']],
    ['Resultado', ['vl_trib_recuperaveis', 'vl_custo_liquido', 'n_linhas', 'n_docs']],
  ]
  const toggle = (k: string) => {
    const n = sel.has(k) ? state.metrics.filter((m) => m !== k) : meta.metrics.map((m) => m.key).filter((m) => sel.has(m) || m === k)
    if (n.length) set({ metrics: n })
  }
  const lbl = Object.fromEntries(meta.metrics.map((m) => [m.key, m]))
  return (
    <div className="w-[520px] p-3">
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        {groups.map(([g, keys]) => (
          <div key={g}>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{g}</div>
            {keys.filter((k) => lbl[k]).map((k) => (
              <label key={k} className="flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-[13px] hover:bg-sunken" onClick={() => toggle(k)}>
                <Checkbox checked={sel.has(k)} onChange={() => toggle(k)} />
                <span className="flex-1">{lbl[k].label}</span>
                {lbl[k].rowLevel && <span className="text-[11px] text-warn">mais lento</span>}
              </label>
            ))}
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-end border-t pt-2">
        <Button size="sm" variant="ghost" onClick={() => set({ metrics: meta.defaultMetrics })}>Restaurar padrão</Button>
      </div>
    </div>
  )
}
