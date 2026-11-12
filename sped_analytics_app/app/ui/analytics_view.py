"""Módulo 2 — Painel de Análise Consolidada: filtros globais, grade multinível (drill / plana / mês a mês),
indicadores, drill-down até a Nota Fiscal, exportação e congelamento de snapshots."""
from __future__ import annotations

import json

import polars as pl
from nicegui import run, ui

from app import config
from app.database import analytics, snapshots
from app.database.analytics import DIMENSIONS, METRICS
from app.database.engine import SpedDatabase
from app.database.filter_builder import FilterError, describe_rules
from app.exporter import excel_writer
from app.ui.common import set_grid, AppState, df_to_rows, fmt_cnpj, fmt_money, grid_options, stamp, totals_row

KPIS = [("vl_contabil", "Valor Contábil"), ("vl_icms", "ICMS"), ("vl_icms_st_fcp", "ICMS-ST + FCP"),
        ("vl_ipi", "IPI"), ("vl_pis", "PIS"), ("vl_cofins", "COFINS"),
        ("vl_trib_recuperaveis", "Tributos Recuperáveis"), ("vl_custo_liquido", "Custo Líquido")]


class AnalyticsView:
    def __init__(self, db: SpedDatabase, state: AppState, save_state):
        self.db = db
        self.state = state
        self.save_state = save_state
        self.export_dir = config.DATA_DIR / "exports"
        self.current_df: pl.DataFrame = pl.DataFrame()
        self._loading = False

    # ------------------------------------------------------------------ layout
    def build(self) -> None:
        with ui.column().classes("w-full gap-3"):
            self._build_filters()
            self._build_toolbar()
            self.crumbs = ui.row().classes("items-center gap-1 w-full")
            self.rules_info = ui.label("").classes("text-xs text-primary")
            self.kpi_row = ui.row().classes("w-full gap-2")
            with ui.splitter(horizontal=True, value=62, limits=(25, 90)).classes("w-full").style(
                    "height: calc(100vh - 330px); min-height: 560px") as sp:
                with sp.before:
                    self.grid = ui.aggrid({"columnDefs": [], "rowData": []}, auto_size_columns=False).classes(
                        "w-full h-full")
                    self.grid.on("cellClicked", self._on_click)
                    self.grid.on("cellDoubleClicked", self._on_dblclick)
                with sp.after:
                    with ui.column().classes("w-full h-full gap-1 pt-2"):
                        with ui.row().classes("w-full items-center"):
                            self.drill_title = ui.label("Clique em uma linha para listar as Notas Fiscais; "
                                                        "duplo clique para descer um nível.").classes(
                                "text-sm font-semibold")
                            ui.space()
                            ui.button("Excel (notas)", icon="download", on_click=self._export_docs).props(
                                "flat dense")
                            ui.button("Excel (itens)", icon="download", on_click=self._export_doc_lines).props(
                                "flat dense")
                        self.docs_grid = ui.aggrid({"columnDefs": [], "rowData": []}, auto_size_columns=False
                                                   ).classes("w-full").style("height: calc(100% - 40px)")
        self.drill_path: list[tuple[str, object]] = []

    def _build_filters(self) -> None:
        gf = self.state.global_filters
        comps = self.db.competencias()
        with ui.card().classes("w-full p-3"):
            with ui.row().classes("w-full items-end gap-2"):
                ui.icon("filter_alt").classes("text-primary self-center")
                self.f_ini = ui.select(comps, value=gf.get("comp_ini"), label="Competência inicial",
                                       clearable=True).classes("w-48")
                self.f_fim = ui.select(comps, value=gf.get("comp_fim"), label="Competência final",
                                       clearable=True).classes("w-48")
                self.f_comps = ui.select(comps, value=gf.get("competencias") or [], multiple=True,
                                         label="Meses específicos", clearable=True).classes("min-w-[190px]").props(
                    "use-chips")
                self.f_filiais = ui.select({}, value=gf.get("filiais") or [], multiple=True, with_input=True,
                                           label="Empresa/Filial (CNPJ/nome)", clearable=True).classes(
                    "min-w-[260px] flex-1").props("use-chips")
                self.f_uf = ui.select([], value=gf.get("ufs_filial") or [], multiple=True, label="UF filial",
                                      clearable=True).classes("w-32").props("use-chips")
                self.f_forn = ui.select({}, value=gf.get("fornecedores") or [], multiple=True, with_input=True,
                                        label="Fornecedor (CNPJ/razão)", clearable=True).classes(
                    "min-w-[260px] flex-1").props("use-chips")
            with ui.row().classes("w-full items-end gap-2"):
                self.f_raiz = ui.input("Raiz CNPJ fornecedor (;)",
                                       value=";".join(gf.get("raizes_fornecedor") or [])).classes("w-48")
                self.f_busca_forn = ui.input("Razão social contém", value=gf.get("busca_fornecedor") or "").classes(
                    "w-48")
                self.f_cfop = ui.select({}, value=gf.get("cfops") or [], multiple=True, with_input=True,
                                        label="CFOP", clearable=True).classes("min-w-[160px]").props("use-chips")
                self.f_cfop_pref = ui.input("CFOP inicia", value=gf.get("cfop_prefixo") or "").classes("w-28")
                self.f_item = ui.select({}, value=gf.get("itens") or [], multiple=True, with_input=True,
                                        label="Item (código/descrição)", clearable=True).classes(
                    "min-w-[220px] flex-1").props("use-chips")
                self.f_busca_item = ui.input("Descrição contém", value=gf.get("busca_item") or "").classes(
                    "w-40")
                self.f_ncm = ui.input("NCM inicia", value=gf.get("ncm_prefixo") or "").classes("w-28")
                ui.button("Aplicar", icon="search", on_click=self.apply_filters)
                ui.button(icon="filter_alt_off", on_click=self.clear_filters).props("flat").tooltip("Limpar filtros")
        self.reload_filter_options()

    def _build_toolbar(self) -> None:
        dims = {k: v[0] for k, v in DIMENSIONS.items()}
        mets = {k: v[0] for k, v in METRICS.items()}
        with ui.row().classes("w-full items-end gap-2"):
            self.t_hier = ui.select(dims, value=list(self.state.hierarchy), multiple=True,
                                    label="Hierarquia (ordem de seleção = ordem dos níveis)",
                                    on_change=self._on_hier_change).classes("min-w-[380px]").props("use-chips")
            self.t_mode = ui.toggle({"drill": "Drill-down", "plana": "Visão plana", "mensal": "Mês a mês"},
                                    value=self.state.mode, on_change=self._on_mode_change)
            self.t_pivot = ui.select(mets, value=self.state.pivot_metric, label="Métrica mês a mês",
                                     on_change=lambda e: self._set("pivot_metric", e.value)).classes("w-56")
            self.t_pivot.bind_visibility_from(self.t_mode, "value", lambda v: v == "mensal")
            with ui.button("Colunas", icon="view_column").props("outline"):
                with ui.menu().classes("p-2"):
                    ui.select(mets, value=list(self.state.metrics), multiple=True, label="Métricas exibidas",
                              on_change=self._on_metrics_change).classes("min-w-[320px]").props("use-chips")
            ui.space()
            with ui.button("Exportar", icon="file_download").props("outline"):
                with ui.menu():
                    ui.menu_item("Excel — grade atual", on_click=self._export_grid)
                    ui.menu_item("Excel — todas as linhas detalhadas (itens)", on_click=lambda: self._export_lines("xlsx"))
                    ui.menu_item("CSV — todas as linhas detalhadas (;)", on_click=lambda: self._export_lines("csv"))
                    ui.menu_item("Parquet — todas as linhas detalhadas", on_click=lambda: self._export_lines("parquet"))
            ui.button("Congelar análise", icon="ac_unit", on_click=self._snapshot_dialog).props("outline")

    # ------------------------------------------------------------------ opções dos filtros
    def reload_filter_options(self) -> None:
        def opts(col: str, fmt=lambda r: f"{r['v']} — {r['l']}") -> dict:
            try:
                return {r["v"]: fmt(r) for r in analytics.distinct_values(self.db, col, limit=5000)}
            except Exception:  # noqa: BLE001
                return {}
        self.f_filiais.options = opts("filial", lambda r: f"{fmt_cnpj(r['v'])} — {r['l']}")
        self.f_forn.options = opts("fornecedor", lambda r: f"{fmt_cnpj(r['v'])} — {r['l']}")
        self.f_cfop.options = opts("cfop", lambda r: r["v"])
        self.f_item.options = opts("item")
        self.f_uf.options = sorted(opts("uf_filial", lambda r: r["v"]).keys())
        comps = self.db.competencias()
        for sel in (self.f_ini, self.f_fim, self.f_comps):
            sel.options = comps
        for sel in (self.f_filiais, self.f_forn, self.f_cfop, self.f_item, self.f_uf, self.f_ini, self.f_fim,
                    self.f_comps):
            if isinstance(sel.value, list):
                sel.value = [v for v in sel.value if v in sel.options]
            elif sel.value not in (sel.options if isinstance(sel.options, list) else sel.options.keys()):
                sel.value = None
            sel.update()

    def collect_filters(self) -> dict:
        def lst(s: str) -> list[str]:
            return [x.strip() for x in (s or "").replace(",", ";").split(";") if x.strip()]
        gf = {"comp_ini": self.f_ini.value, "comp_fim": self.f_fim.value, "competencias": self.f_comps.value or [],
              "filiais": self.f_filiais.value or [], "ufs_filial": self.f_uf.value or [],
              "fornecedores": self.f_forn.value or [], "raizes_fornecedor": lst(self.f_raiz.value),
              "busca_fornecedor": (self.f_busca_forn.value or "").strip(), "cfops": self.f_cfop.value or [],
              "cfop_prefixo": (self.f_cfop_pref.value or "").strip(), "itens": self.f_item.value or [],
              "busca_item": (self.f_busca_item.value or "").strip(), "ncm_prefixo": (self.f_ncm.value or "").strip()}
        return {k: v for k, v in gf.items() if v}

    def set_filters(self, gf: dict) -> None:
        self.f_ini.value, self.f_fim.value = gf.get("comp_ini"), gf.get("comp_fim")
        self.f_comps.value = gf.get("competencias") or []
        self.f_filiais.value = [v for v in gf.get("filiais") or [] if v in self.f_filiais.options]
        self.f_uf.value = gf.get("ufs_filial") or []
        self.f_forn.value = [v for v in gf.get("fornecedores") or [] if v in self.f_forn.options]
        self.f_raiz.value = ";".join(gf.get("raizes_fornecedor") or [])
        self.f_busca_forn.value = gf.get("busca_fornecedor") or ""
        self.f_cfop.value = [v for v in gf.get("cfops") or [] if v in self.f_cfop.options]
        self.f_cfop_pref.value = gf.get("cfop_prefixo") or ""
        self.f_item.value = [v for v in gf.get("itens") or [] if v in self.f_item.options]
        self.f_busca_item.value = gf.get("busca_item") or ""
        self.f_ncm.value = gf.get("ncm_prefixo") or ""

    async def apply_filters(self) -> None:
        self.state.global_filters = self.collect_filters()
        self.state.path = []
        self.save_state()
        await self.refresh()

    async def clear_filters(self) -> None:
        self.set_filters({})
        self.state.applied_filter_name = ""
        self.state.rules = {"op": "AND", "rules": []}
        await self.apply_filters()

    # ------------------------------------------------------------------ eventos da barra
    def _set(self, key: str, value) -> None:
        setattr(self.state, key, value)
        self.save_state()
        ui.timer(0.01, self.refresh, once=True)

    def _on_hier_change(self, e) -> None:
        if not e.value:
            ui.notify("A hierarquia precisa de ao menos uma dimensão", type="warning")
            return
        self.state.hierarchy = list(e.value)
        self.state.path = []
        self.save_state()
        ui.timer(0.01, self.refresh, once=True)

    def _on_mode_change(self, e) -> None:
        self.state.mode = e.value
        self.state.path = []
        self.save_state()
        ui.timer(0.01, self.refresh, once=True)

    def _on_metrics_change(self, e) -> None:
        if e.value:
            self.state.metrics = list(e.value)
            self.save_state()
            ui.timer(0.01, self.refresh, once=True)

    # ------------------------------------------------------------------ consulta principal
    def _level_dims(self) -> list[str]:
        h = self.state.hierarchy
        if self.state.mode == "plana":
            return list(h)
        lvl = min(len(self.state.path), len(h) - 1)
        return [h[lvl]]

    async def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            gf, rules = self.state.global_filters, self.state.rules
            path = self.state.path_tuples() if self.state.mode != "plana" else []
            dims = self._level_dims()
            metrics = self.state.metrics
            try:
                if self.state.mode == "mensal":
                    df = await run.io_bound(analytics.monthly_pivot, self.db, gf, rules, dims,
                                            self.state.pivot_metric, path)
                else:
                    df = await run.io_bound(analytics.aggregate, self.db, gf, rules, dims, metrics, path)
                tot = await run.io_bound(analytics.totals, self.db, gf, rules,
                                         [k for k, _ in KPIS] + ["n_docs", "n_linhas"], path)
            except FilterError as e:
                ui.notify(f"Filtro inválido: {e}", type="negative")
                return
            self.current_df = df
            self._render_grid(df, dims)
            self._render_kpis(tot)
            self._render_crumbs()
            desc = describe_rules(rules)
            self.rules_info.text = (f"Regras ativas{' [' + self.state.applied_filter_name + ']' if self.state.applied_filter_name else ''}: "
                                    f"{desc}") if desc else ""
        finally:
            self._loading = False

    def _render_grid(self, df: pl.DataFrame, dims: list[str]) -> None:
        pin = sum(1 for c in df.columns if c in dims or c.endswith("__desc"))
        first = df.columns[0] if df.columns else None
        tot = totals_row(df, first) if df.height else None
        if tot and first:
            for c in df.columns:
                if c.endswith("__desc") or c in dims[1:]:
                    tot[c] = ""
        opts = grid_options(df, pin_first=min(pin, 4), totals=tot, extra={"rowHeight": 30, "headerHeight": 36})
        set_grid(self.grid, opts)

        if df.height >= config.UI_MAX_GRID_ROWS:
            ui.notify(f"Exibindo as {config.UI_MAX_GRID_ROWS:,} maiores linhas; use exportação para o conjunto "
                      "completo".replace(",", "."), type="info")

    def _render_kpis(self, tot: dict) -> None:
        self.kpi_row.clear()
        with self.kpi_row:
            for k, label in KPIS:
                with ui.card().classes("p-2 flex-1 min-w-[140px]"):
                    ui.label(label).classes("text-xs opacity-70")
                    ui.label(fmt_money(tot.get(k))).classes("text-base font-semibold")
            with ui.card().classes("p-2 min-w-[120px]"):
                ui.label("Documentos / Linhas").classes("text-xs opacity-70")
                ui.label(f"{int(tot.get('n_docs') or 0):,} / {int(tot.get('n_linhas') or 0):,}".replace(",", ".")
                         ).classes("text-base font-semibold")

    def _render_crumbs(self) -> None:
        self.crumbs.clear()
        h = self.state.hierarchy
        with self.crumbs:
            ui.icon("account_tree").classes("text-primary")
            if self.state.mode == "plana":
                ui.label("Visão plana: " + " → ".join(DIMENSIONS[d][0] for d in h)).classes("text-sm")
                return
            ui.button("Todos", on_click=lambda: self._go_level(0)).props("flat dense no-caps")
            for i, (dim, _val, lbl) in enumerate(self.state.path):
                ui.icon("chevron_right")
                ui.button(f"{DIMENSIONS[dim][0]}: {lbl}", on_click=lambda i=i: self._go_level(i + 1)).props(
                    "flat dense no-caps")
            lvl = min(len(self.state.path), len(h) - 1)
            ui.icon("chevron_right")
            ui.label(f"Nível atual: {DIMENSIONS[h[lvl]][0]}" +
                     (f"  (próximo: {DIMENSIONS[h[lvl + 1]][0]})" if lvl + 1 < len(h) else "  (último nível)")
                     ).classes("text-sm font-semibold")

    async def _go_level(self, n: int) -> None:
        self.state.path = self.state.path[:n]
        self.save_state()
        await self.refresh()

    # ------------------------------------------------------------------ drill-down
    def _row_path(self, data: dict) -> list[tuple[str, object, str]] | None:
        if not data or data.get(self.current_df.columns[0] if self.current_df.columns else "") == "TOTAL":
            return None
        dims = self._level_dims()
        out = []
        for d in dims:
            if d not in data:
                return None
            v = data[d]
            lbl = str(v) if v is not None else "(vazio)"
            if f"{d}__desc" in data and data[f"{d}__desc"]:
                lbl = f"{fmt_cnpj(lbl)} {data[f'{d}__desc']}"
            out.append((d, v, lbl[:60]))
        return out

    async def _on_click(self, e) -> None:
        data = e.args.get("data") if isinstance(e.args, dict) else None
        if e.args.get("rowPinned"):
            return
        rp = self._row_path(data)
        if rp is None:
            return
        base = self.state.path_tuples() if self.state.mode != "plana" else []
        self.drill_path = base + [(d, v) for d, v, _ in rp]
        self.drill_title.text = "Notas Fiscais: " + " | ".join(lbl for _, _, lbl in
                                                                 (self.state.path if self.state.mode != "plana" else [])
                                                                 + rp)
        df = await run.io_bound(analytics.documents, self.db, self.state.global_filters, self.state.rules,
                                self.drill_path)
        self.docs_df = df
        set_grid(self.docs_grid, grid_options(df, pin_first=3, totals=totals_row(df, "competencia"),
                                                   hide={"file_id", "doc_id"}))


    async def _on_dblclick(self, e) -> None:
        if self.state.mode == "plana" or e.args.get("rowPinned"):
            return
        data = e.args.get("data")
        rp = self._row_path(data)
        if rp is None:
            return
        if len(self.state.path) + 1 >= len(self.state.hierarchy):
            ui.notify("Último nível da hierarquia — notas listadas no painel inferior", type="info")
            return
        self.state.path = self.state.path + [list(rp[0])]
        self.save_state()
        await self.refresh()

    # ------------------------------------------------------------------ exportação
    def _context(self) -> dict:
        return {"Gerado em": stamp(), "Filtros globais": json.dumps(self.state.global_filters, ensure_ascii=False),
                "Regras": describe_rules(self.state.rules) or "(nenhuma)",
                "Filtro salvo": self.state.applied_filter_name or "",
                "Hierarquia": " → ".join(DIMENSIONS[d][0] for d in self.state.hierarchy),
                "Caminho": " > ".join(p[2] for p in self.state.path), "Modo": self.state.mode}

    async def _export_grid(self) -> None:
        if self.current_df.is_empty():
            ui.notify("Grade vazia", type="warning")
            return
        p = self.export_dir / f"analise_consolidada_{stamp()}.xlsx"
        await run.io_bound(excel_writer.export_frames_excel, p, {"Analise": self.current_df}, self._context())
        self._delivered(p)

    async def _export_lines(self, fmt: str) -> None:
        sql, params = analytics.lines_sql(self.state.global_filters, self.state.rules,
                                          self.state.path_tuples() if self.state.mode != "plana" else [])
        n = ui.notification("Exportando...", spinner=True, timeout=None)
        try:
            p = self.export_dir / f"entradas_detalhadas_{stamp()}.{fmt}"
            if fmt == "xlsx":
                await run.io_bound(excel_writer.export_query_excel, self.db, sql, params, p, "Itens", self._context())
            elif fmt == "csv":
                await run.io_bound(excel_writer.export_query_csv, self.db, sql, params, p)
            else:
                await run.io_bound(excel_writer.export_query_parquet, self.db, sql, params, p)
        finally:
            n.dismiss()
        self._delivered(p)

    async def _export_docs(self) -> None:
        df = getattr(self, "docs_df", None)
        if df is None or df.is_empty():
            ui.notify("Selecione uma linha para listar as notas", type="warning")
            return
        p = self.export_dir / f"notas_drilldown_{stamp()}.xlsx"
        await run.io_bound(excel_writer.export_frames_excel, p, {"Notas": df}, {**self._context(),
                                                                               "Seleção": self.drill_title.text})
        self._delivered(p)

    async def _export_doc_lines(self) -> None:
        if not getattr(self, "drill_path", None):
            ui.notify("Selecione uma linha para listar as notas", type="warning")
            return
        sql, params = analytics.lines_sql(self.state.global_filters, self.state.rules, self.drill_path)
        p = self.export_dir / f"itens_drilldown_{stamp()}.xlsx"
        await run.io_bound(excel_writer.export_query_excel, self.db, sql, params, p, "Itens",
                           {**self._context(), "Seleção": self.drill_title.text})
        self._delivered(p)

    def _delivered(self, p) -> None:
        ui.notify(f"Arquivo gerado: {p}", type="positive", multi_line=True, close_button=True, timeout=8000)
        ui.download(p)

    # ------------------------------------------------------------------ snapshots
    def _snapshot_dialog(self) -> None:
        if self.current_df.is_empty():
            ui.notify("Nada a congelar: grade vazia", type="warning")
            return
        with ui.dialog() as d, ui.card().classes("min-w-[520px]"):
            ui.label("Congelar análise (snapshot imutável)").classes("text-lg font-semibold")
            nome = ui.input("Nome", value=f"Análise {stamp()}").classes("w-full")
            notas = ui.textarea("Anotações técnicas").classes("w-full")
            ui.label(f"{self.current_df.height} linha(s) da grade atual serão preservadas com filtros e contexto."
                     ).classes("text-sm opacity-70")

            async def salvar() -> None:
                ctx = {**self._context(), "state": self.state.to_dict()}
                sid = await run.io_bound(snapshots.save_snapshot, self.db, nome.value or "Snapshot", notas.value or "",
                                         ctx, self.current_df)
                d.close()
                ui.notify(f"Snapshot #{sid} salvo", type="positive")
                if self.on_snapshot_saved:
                    self.on_snapshot_saved()

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancelar", on_click=d.close).props("flat")
                ui.button("Salvar", icon="save", on_click=salvar)
        d.open()

    on_snapshot_saved = None
