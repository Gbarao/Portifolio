"""Módulo 4 — Auditoria de Divergências SPED Fiscal x EFD-Contribuições."""
from __future__ import annotations

from nicegui import run, ui

from app import config
from app.database import audit
from app.database.engine import SpedDatabase
from app.exporter import excel_writer
from app.ui.common import set_grid, AppState, grid_options, stamp, totals_row


class AuditView:
    def __init__(self, db: SpedDatabase, state: AppState):
        self.db = db
        self.state = state
        self.current = None
        self.df = None

    def build(self) -> None:
        with ui.column().classes("w-full gap-3"):
            with ui.row().classes("w-full items-center"):
                ui.label("Auditoria de Divergências (Cruzamento Automático)").classes("text-lg font-semibold")
                ui.space()
                self.tol = ui.number("Tolerância (R$)", value=config.TOLERANCIA_DIVERGENCIA, min=0, step=0.01,
                                     format="%.2f").classes("w-36")
                ui.button("Executar todas", icon="fact_check", on_click=self.run_all)
                ui.button("Exportar todas (Excel)", icon="download", on_click=self.export_all).props("outline")
            ui.label("Usa o período e as filiais definidos nos Filtros Globais da Análise Consolidada.").classes(
                "text-sm opacity-70")
            self.cards = ui.row().classes("w-full gap-2")
            self.title = ui.label("").classes("text-md font-semibold")
            with ui.row().classes("w-full items-center"):
                ui.space()
                ui.button("Exportar verificação", icon="download", on_click=self.export_one).props("flat dense")
            self.grid = ui.aggrid({"columnDefs": [], "rowData": []}, auto_size_columns=False).classes("w-full").style(
                "height: calc(100vh - 420px); min-height: 420px")
        self._render_cards({})

    def _render_cards(self, counts: dict) -> None:
        self.cards.clear()
        with self.cards:
            for k, label in audit.CHECKS.items():
                n = counts.get(k)
                color = "positive" if n == 0 else ("negative" if isinstance(n, int) and n > 0 else "grey")
                with ui.card().classes("p-3 w-[300px] cursor-pointer").on("click", lambda k=k: self.open_check(k)):
                    with ui.row().classes("items-center no-wrap gap-2"):
                        ui.badge("—" if n is None else str(n), color=color)
                        ui.label(label).classes("text-sm")

    async def run_all(self) -> None:
        gf = self.state.global_filters
        n = ui.notification("Executando verificações...", spinner=True, timeout=None)
        try:
            res = await run.io_bound(audit.summary, self.db, gf)
        finally:
            n.dismiss()
        self._render_cards({r["verificacao"]: r["ocorrencias"] for r in res})

    async def open_check(self, k: str) -> None:
        df = await run.io_bound(audit.run_check, self.db, k, self.state.global_filters, float(self.tol.value or 0))
        self.current, self.df = k, df
        self.title.text = f"{audit.CHECKS[k]} — {df.height} ocorrência(s)"
        set_grid(self.grid, grid_options(df, pin_first=2, totals=totals_row(df, df.columns[0]) if df.height else None))


    async def export_one(self) -> None:
        if self.df is None:
            ui.notify("Abra uma verificação", type="warning")
            return
        p = config.DATA_DIR / "exports" / f"auditoria_{self.current}_{stamp()}.xlsx"
        await run.io_bound(excel_writer.export_frames_excel, p, {self.current[:31]: self.df},
                           {"Verificação": audit.CHECKS[self.current], "Filtros": str(self.state.global_filters)})
        ui.download(p)

    async def export_all(self) -> None:
        n = ui.notification("Gerando relatório de auditoria...", spinner=True, timeout=None)
        try:
            gf, tol = self.state.global_filters, float(self.tol.value or 0)
            sheets = {}
            for k in audit.CHECKS:
                sheets[k[:31]] = await run.io_bound(audit.run_check, self.db, k, gf, tol)
            p = config.DATA_DIR / "exports" / f"auditoria_completa_{stamp()}.xlsx"
            info = {"Filtros": str(gf), "Tolerância": str(tol)}
            info.update({k: f"{audit.CHECKS[k]}: {sheets[k[:31]].height} ocorrência(s)" for k in audit.CHECKS})
            await run.io_bound(excel_writer.export_frames_excel, p, sheets, info)
        finally:
            n.dismiss()
        ui.download(p)
