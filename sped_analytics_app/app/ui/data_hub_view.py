"""Módulo 1 — Central de Arquivos (Data Hub): importação em lote, matriz de cobertura, gestão da base e backup."""
from __future__ import annotations

from pathlib import Path

import polars as pl
from nicegui import app, run, ui

from app import config
from app.database.engine import SpedDatabase
from app.ui.common import df_to_rows, fmt_cnpj, grid_options, stamp

STATUS_STYLE = {
    "AMBOS": ("✔ SF + EFD", "#1b5e20", "#c8e6c9"),
    "SF": ("SF (falta EFD)", "#8a5300", "#ffe0b2"),
    "EC": ("EFD (falta SF)", "#0d47a1", "#bbdefb"),
    "": ("✗ ausente", "#b71c1c", "#ffcdd2"),
}


class Progress:
    def __init__(self):
        self.msg = ""
        self.frac = 0.0
        self.running = False

    def __call__(self, msg: str, frac: float) -> None:
        self.msg, self.frac = msg, frac


class DataHubView:
    def __init__(self, db: SpedDatabase, on_data_changed):
        self.db = db
        self.on_data_changed = on_data_changed
        self.progress = Progress()
        self.upload_dir = config.DATA_DIR / "uploads"

    # ------------------------------------------------------------------ layout
    def build(self) -> None:
        with ui.column().classes("w-full gap-4"):
            self._build_stats()
            with ui.row().classes("w-full gap-4 items-stretch no-wrap max-lg:flex-wrap"):
                self._build_import_card()
                self._build_manage_card()
            self._build_coverage()
            self._build_files()
        ui.timer(0.4, self._tick)

    @ui.refreshable_method
    def _build_stats(self) -> None:
        s = self.db.stats()
        with ui.row().classes("w-full gap-3"):
            for label, value, icon in (
                ("Arquivos ativos", f"{s['arquivos']}  (SF {s['arquivos_sf']} | EFD {s['arquivos_ec']})", "description"),
                ("Linhas consolidadas", f"{s['linhas_fato']:,}".replace(",", "."), "table_rows"),
                ("Filiais", str(s["filiais"]), "store"),
                ("Competências", str(s["competencias"]), "calendar_month"),
                ("Banco DuckDB", f"{s['db_mb']:.1f} MB", "storage"),
                ("Cache Parquet", f"{s['parquet_mb']:.1f} MB", "inventory_2"),
            ):
                with ui.card().classes("p-3 min-w-[170px] flex-1"):
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.icon(icon, size="sm").classes("text-primary")
                        ui.label(label).classes("text-xs opacity-70")
                    ui.label(value).classes("text-lg font-semibold")

    def _build_import_card(self) -> None:
        with ui.card().classes("flex-1 min-w-[420px]"):
            ui.label("Importador em Lote").classes("text-lg font-semibold")
            ui.label("Informe uma pasta (subpastas incluídas) ou arquivo .txt. SPED Fiscal e EFD-Contribuições são "
                     "identificados automaticamente pelo registro 0000.").classes("text-sm opacity-70")
            with ui.row().classes("w-full items-center no-wrap"):
                self.path_input = ui.input("Pasta ou arquivo", placeholder=r"C:\SPED\2024  ou  /dados/sped").classes(
                    "flex-1").props("clearable")
                if app.native.main_window is not None or getattr(app, "_sped_native", False):
                    ui.button(icon="folder_open", on_click=self._pick_folder).props("flat").tooltip("Selecionar pasta")
            with ui.row().classes("items-center gap-3"):
                self.workers = ui.number("Processos paralelos", value=config.PARSER_WORKERS, min=1,
                                         max=max(1, config.CPU_COUNT), step=1).classes("w-44")
                self.btn_import = ui.button("Importar", icon="upload_file", on_click=self._import_path)
            ui.separator()
            ui.label("Ou arraste os arquivos .txt aqui (copiados para o cofre local antes da importação):").classes(
                "text-sm opacity-70")
            ui.upload(multiple=True, auto_upload=True, on_multi_upload=self._on_upload,
                      label="Soltar arquivos SPED").props('accept=".txt,.TXT" flat bordered').classes("w-full")
            self.prog_bar = ui.linear_progress(value=0, show_value=False).classes("mt-2")
            self.prog_label = ui.label("").classes("text-sm")
            self.result_area = ui.column().classes("w-full gap-1")

    def _build_manage_card(self) -> None:
        with ui.card().classes("flex-1 min-w-[380px]"):
            ui.label("Gestão da Base e Backup").classes("text-lg font-semibold")
            with ui.row().classes("items-end gap-2 w-full"):
                self.rm_comps = ui.select(self.db.competencias(), multiple=True, label="Competências").classes(
                    "min-w-[180px] flex-1").props("use-chips")
                self.rm_tipo = ui.select({"": "Ambos", "ICMS_IPI": "SPED Fiscal", "CONTRIB": "EFD-Contribuições"},
                                         value="", label="Tipo").classes("w-44")
                ui.button("Remover", icon="delete", color="negative", on_click=self._remove_comps)
            ui.separator()
            with ui.row().classes("items-center gap-2"):
                self.bk_parquet = ui.switch("Incluir cache Parquet", value=False)
                ui.button("Gerar backup", icon="backup", on_click=self._backup)
            with ui.row().classes("items-end gap-2 w-full no-wrap"):
                self.restore_path = ui.input("Arquivo de backup (.zip) para restaurar").classes("flex-1")
                ui.button("Restaurar", icon="restore", color="warning", on_click=self._restore)
            ui.separator()
            with ui.row().classes("gap-2"):
                ui.button("Reconsolidar toda a base", icon="sync", on_click=self._rebuild_all).props("outline")
                ui.button("Log de importação", icon="receipt_long", on_click=self._show_log).props("outline")
            ui.label(f"Cofre local: {config.DATA_DIR}").classes("text-xs opacity-60 break-all")

    @ui.refreshable_method
    def _build_coverage(self) -> None:
        df = self.db.coverage_matrix()
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center w-full"):
                ui.label("Matriz de Cobertura Fiscal").classes("text-lg font-semibold")
                ui.space()
                for k, (txt, fg, bg) in STATUS_STYLE.items():
                    ui.label(txt).classes("text-xs px-2 py-1 rounded").style(f"color:{fg};background:{bg}")
            if df.is_empty():
                ui.label("Nenhum arquivo importado.").classes("opacity-60")
                return
            piv = df.pivot(on="competencia", index=["cnpj", "nome", "uf"], values="status",
                           aggregate_function="first").sort("cnpj")
            comps = sorted(c for c in piv.columns if c not in ("cnpj", "nome", "uf"))
            faltas = sum(1 for r in df.to_dicts() if r["status"] != "AMBOS")
            ui.label(f"{piv.height} estabelecimento(s) x {len(comps)} competência(s) — {faltas} lacuna(s) de "
                     "cobertura").classes("text-sm opacity-70")
            style_js = ("params => ({'AMBOS': {color:'#1b5e20', backgroundColor:'#c8e6c9'}, 'SF': {color:'#8a5300', "
                        "backgroundColor:'#ffe0b2'}, 'EC': {color:'#0d47a1', backgroundColor:'#bbdefb'}})[params.value] "
                        "|| {color:'#b71c1c', backgroundColor:'#ffcdd2'}")
            fmt_js = ("params => ({'AMBOS': '✔ SF+EFD', 'SF': 'SF', 'EC': 'EFD'})[params.value] || '✗'")
            cols = [{"field": "cnpj", "headerName": "CNPJ", "pinned": "left", "minWidth": 170,
                     ":valueFormatter": "p => " + "(p.value||'').replace(/^(\\d{2})(\\d{3})(\\d{3})(\\d{4})(\\d{2})$/, "
                                                  "'$1.$2.$3/$4-$5')"},
                    {"field": "nome", "headerName": "Estabelecimento", "pinned": "left", "minWidth": 220},
                    {"field": "uf", "headerName": "UF", "width": 70}]
            cols += [{"field": c, "headerName": c, ":cellStyle": style_js, ":valueFormatter": fmt_js, "width": 110,
                      "cellClass": "text-center"} for c in comps]
            ui.aggrid({"columnDefs": cols, "rowData": piv.fill_null("").to_dicts(),
                       "defaultColDef": {"sortable": True, "resizable": True, "filter": True}},
                      auto_size_columns=False).classes("w-full").style(
                f"height: {min(120 + 34 * piv.height, 520)}px")

    @ui.refreshable_method
    def _build_files(self) -> None:
        df = self.db.list_files()
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center w-full"):
                ui.label("Arquivos Importados (ativos)").classes("text-lg font-semibold")
                ui.space()
                ui.button("Remover selecionados", icon="delete_sweep", color="negative",
                          on_click=self._remove_selected).props("outline")
            opts = grid_options(df, pin_first=0)
            opts["rowSelection"] = {"mode": "multiRow", "checkboxes": True, "headerCheckbox": True}
            for c in opts["columnDefs"]:
                if c["field"] == "cnpj":
                    c["headerName"] = "CNPJ (0000)"
                if c["field"] == "id_arquivo":
                    c["headerName"] = "ID"
                    c["maxWidth"] = 90
                if c["field"] in ("tipo_sped", "competencia", "finalidade"):
                    c["headerName"] = {"tipo_sped": "Tipo", "competencia": "Competência",
                                       "finalidade": "Finalidade"}[c["field"]]
            self.files_grid = ui.aggrid(opts, auto_size_columns=False).classes("w-full h-80")

    # ------------------------------------------------------------------ ações
    def _tick(self) -> None:
        if self.progress.running:
            self.prog_bar.value = self.progress.frac
            self.prog_label.text = self.progress.msg

    async def _pick_folder(self) -> None:
        try:
            import webview  # type: ignore
            res = await app.native.main_window.create_file_dialog(webview.FOLDER_DIALOG)
            if res:
                self.path_input.value = res[0]
        except Exception as e:  # noqa: BLE001
            ui.notify(f"Seleção de pasta indisponível: {e}", type="warning")

    async def _import_path(self) -> None:
        p = (self.path_input.value or "").strip().strip('"')
        if not p or not Path(p).exists():
            ui.notify("Informe uma pasta ou arquivo existente", type="warning")
            return
        await self._run_import([p])

    async def _on_upload(self, e) -> None:
        dest = self.upload_dir / stamp()
        dest.mkdir(parents=True, exist_ok=True)
        for f in e.files:
            await f.save(dest / Path(f.name).name)
        await self._run_import([str(dest)])

    async def _run_import(self, paths: list[str]) -> None:
        if self.progress.running:
            ui.notify("Já existe uma importação em andamento", type="warning")
            return
        self.progress.running = True
        self.btn_import.disable()
        self.result_area.clear()
        try:
            summary = await run.io_bound(self.db.import_paths, paths, self.progress, int(self.workers.value or 1))
        except Exception as e:  # noqa: BLE001
            ui.notify(f"Falha na importação: {e}", type="negative", multi_line=True, close_button=True)
            return
        finally:
            self.progress.running = False
            self.btn_import.enable()
        self.prog_bar.value = 1
        self.prog_label.text = (f"Concluído em {summary.segundos:.1f}s — importados {summary.count('IMPORTADO')}, "
                                f"substituídos {summary.count('SUBSTITUIDO')}, duplicados {summary.count('DUPLICADO')}, "
                                f"ignorados {summary.count('IGNORADO')}, erros {summary.count('ERRO')}")
        colors = {"IMPORTADO": "positive", "SUBSTITUIDO": "info", "DUPLICADO": "grey", "IGNORADO": "warning",
                  "ERRO": "negative"}
        with self.result_area:
            for r in summary.resultados[:300]:
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.badge(r.acao, color=colors.get(r.acao, "grey"))
                    ui.label(f"{Path(r.arquivo).name} — {r.tipo} {fmt_cnpj(r.cnpj)} {r.competencia} {r.mensagem}"
                             ).classes("text-xs")
        self.refresh()
        self.on_data_changed()

    def refresh(self) -> None:
        self._build_stats.refresh()
        self._build_coverage.refresh()
        self._build_files.refresh()
        self.rm_comps.options = self.db.competencias()
        self.rm_comps.update()

    async def _remove_selected(self) -> None:
        rows = await self.files_grid.get_selected_rows()
        ids = [r["id_arquivo"] for r in rows]
        if not ids:
            ui.notify("Selecione arquivos na grade", type="warning")
            return
        if not await self._confirm(f"Remover {len(ids)} arquivo(s) e seus dados da base?"):
            return
        comps = await run.io_bound(self.db.remove_files, ids)
        ui.notify(f"Removidos. Competências reconsolidadas: {', '.join(comps)}", type="positive")
        self.refresh()
        self.on_data_changed()

    async def _remove_comps(self) -> None:
        comps = self.rm_comps.value or []
        if not comps:
            ui.notify("Selecione competências", type="warning")
            return
        if not await self._confirm(f"Remover {'todos os arquivos' if not self.rm_tipo.value else self.rm_tipo.value} "
                                   f"das competências {', '.join(comps)}?"):
            return
        await run.io_bound(self.db.remove_competencias, comps, self.rm_tipo.value or None)
        ui.notify("Competências removidas", type="positive")
        self.refresh()
        self.on_data_changed()

    async def _backup(self) -> None:
        n = ui.notification("Gerando backup...", spinner=True, timeout=None)
        try:
            path = await run.io_bound(self.db.backup, None, bool(self.bk_parquet.value))
        finally:
            n.dismiss()
        ui.notify(f"Backup salvo em {path}", type="positive", multi_line=True, close_button=True, timeout=0)
        ui.download(path)

    async def _restore(self) -> None:
        p = (self.restore_path.value or "").strip().strip('"')
        if not p or not Path(p).exists():
            ui.notify("Informe o caminho do .zip de backup", type="warning")
            return
        if not await self._confirm("Restaurar substituirá a base atual (uma cópia de segurança será mantida). Continuar?"):
            return
        try:
            await run.io_bound(self.db.restore, p)
        except Exception as e:  # noqa: BLE001
            ui.notify(f"Falha ao restaurar: {e}", type="negative")
            return
        ui.notify("Base restaurada", type="positive")
        self.refresh()
        self.on_data_changed()

    async def _rebuild_all(self) -> None:
        n = ui.notification("Reconsolidando toda a base...", spinner=True, timeout=None)
        try:
            r = await run.io_bound(self.db.rebuild_fato, None)
        finally:
            n.dismiss()
        ui.notify(f"{r['linhas']:,} linhas consolidadas em {r['segundos']:.1f}s".replace(",", "."), type="positive")
        self.refresh()
        self.on_data_changed()

    def _show_log(self) -> None:
        df = self.db.import_log()
        with ui.dialog().props("maximized") as d, ui.card().classes("w-full h-full"):
            with ui.row().classes("w-full items-center"):
                ui.label("Log de Importação").classes("text-lg font-semibold")
                ui.space()
                ui.button(icon="close", on_click=d.close).props("flat round")
            ui.aggrid(grid_options(df)).classes("w-full").style("height: calc(100vh - 120px)")
        d.open()

    async def _confirm(self, text: str) -> bool:
        with ui.dialog() as d, ui.card():
            ui.label(text)
            with ui.row().classes("justify-end w-full"):
                ui.button("Cancelar", on_click=lambda: d.submit(False)).props("flat")
                ui.button("Confirmar", color="negative", on_click=lambda: d.submit(True))
        return bool(await d)
