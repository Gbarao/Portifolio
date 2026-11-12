"""Ponto de entrada: Sistema Local de Inteligência e Consolidação Fiscal (SPED Fiscal + EFD-Contribuições).

Uso:
    python -m app.main                 # abre a aplicação (janela nativa se pywebview estiver instalado)
    python -m app.main --browser       # força abertura no navegador local (127.0.0.1)
    python -m app.main --importar DIR  # importa uma pasta sem abrir a interface
    python -m app.main --reconsolidar  # reconstrói a tabela fato
    python -m app.main --demo          # gera arquivos SPED de exemplo e importa
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402


def _cli_import(paths: list[str]) -> None:
    from app.database.engine import get_db
    db = get_db()
    summary = db.import_paths(paths, progress=lambda m, f: print(f"[{f * 100:5.1f}%] {m}", flush=True))
    for r in summary.resultados:
        print(f"{r.acao:12s} {Path(r.arquivo).name} {r.tipo} {r.cnpj} {r.competencia} {r.mensagem}")
    print(f"Concluído em {summary.segundos:.1f}s; competências reconsolidadas: {summary.competencias_reconsolidadas}")


def build_ui(native: bool) -> None:
    from nicegui import app, ui

    from app.database import filter_builder as fb
    from app.database import snapshots
    from app.database.engine import get_db
    from app.ui.analytics_view import AnalyticsView
    from app.ui.audit_view import AuditView
    from app.ui.common import AppState
    from app.ui.data_hub_view import DataHubView
    from app.ui.query_builder_ui import QueryBuilderView

    db = get_db()
    app._sped_native = native  # type: ignore[attr-defined]
    app.on_shutdown(db.close)

    @ui.page("/")
    def index() -> None:
        state = AppState.from_dict(db.session_get("ui_state"))
        dark = ui.dark_mode(value=db.session_get("dark_mode", None))
        ui.colors(primary="#1F3864", secondary="#2E75B6", accent="#00897B")
        ui.add_css(".nicegui-content{padding:12px 16px} .q-tab{min-height:42px} "
                   "@layer theme{.body--dark .text-primary{color:#9ec1ff !important} "
                   ".body--dark .bg-blue-50{background:#1e293b !important}}")

        def save_state() -> None:
            db.session_set("ui_state", state.to_dict())

        views: dict = {}

        async def apply_to_analysis() -> None:
            tabs.value = "analise"
            state.tab = "analise"
            state.path = []
            save_state()
            await views["analytics"].refresh()

        async def apply_preset(f: dict) -> None:
            d = f.get("definicao") or {}
            state.rules = d.get("rules") or {"op": "AND", "rules": []}
            if d.get("global") is not None:
                state.global_filters = d.get("global") or {}
                views["analytics"].set_filters(state.global_filters)
            view = d.get("view") or {}
            if view.get("hierarchy"):
                state.hierarchy = view["hierarchy"]
                views["analytics"].t_hier.value = list(state.hierarchy)
            if view.get("mode"):
                state.mode = view["mode"]
                views["analytics"].t_mode.value = state.mode
            if view.get("metrics"):
                state.metrics = view["metrics"]
            state.applied_filter_name = f.get("nome", "")
            views["qb"].load_rules(state.rules)
            ui.notify(f"Filtro aplicado: {state.applied_filter_name}", type="positive")
            await apply_to_analysis()

        def on_data_changed() -> None:
            views["analytics"].reload_filter_options()
            ui.timer(0.05, views["analytics"].refresh, once=True)
            refresh_drawer()

        # ---------------- cabeçalho
        with ui.header(elevated=True).classes("items-center gap-3 px-4 py-1"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round color=white")
            ui.icon("account_balance").classes("text-2xl")
            with ui.column().classes("gap-0"):
                ui.label("Consolidação Fiscal de Entradas").classes("text-lg font-semibold leading-tight")
                ui.label("SPED Fiscal (ICMS/IPI) × EFD-Contribuições (PIS/COFINS) — 100% local").classes(
                    "text-xs opacity-80 leading-tight")
            ui.space()
            with ui.tabs(value=state.tab if state.tab in ("hub", "analise", "filtros", "auditoria") else "analise",
                         on_change=lambda e: (setattr(state, "tab", e.value), save_state())) as tabs:
                ui.tab("hub", label="Central de Arquivos", icon="folder_copy")
                ui.tab("analise", label="Análise Consolidada", icon="table_view")
                ui.tab("filtros", label="Filtros & Biblioteca", icon="tune")
                ui.tab("auditoria", label="Auditoria", icon="fact_check")
            ui.space()

            def toggle_dark() -> None:
                dark.value = not dark.value
                db.session_set("dark_mode", dark.value)

            ui.button(icon="dark_mode", on_click=toggle_dark).props("flat round color=white").tooltip(
                "Tema claro/escuro")

        # ---------------- lista lateral de acesso rápido
        with ui.left_drawer(value=False, bordered=True).classes("p-3") as drawer:
            drawer_col = ui.column().classes("w-full gap-1")

        def refresh_drawer() -> None:
            drawer_col.clear()
            with drawer_col:
                ui.label("Filtros salvos (1 clique)").classes("text-sm font-semibold")
                fl = fb.list_filters(db)
                if not fl:
                    ui.label("—").classes("opacity-60")
                for f in fl:
                    ui.button(f"{f['nome']}", icon="bolt", on_click=lambda f=f: apply_preset(f)).props(
                        "flat dense no-caps align=left").classes("w-full justify-start").tooltip(f["categoria"])
                ui.separator()
                ui.label("Snapshots").classes("text-sm font-semibold")
                for s in snapshots.list_snapshots(db)[:50]:
                    ui.button(f"#{s['id']} {s['nome']}", icon="ac_unit",
                              on_click=lambda s=s: views["qb"].open_snapshot(s["id"])).props(
                        "flat dense no-caps align=left").classes("w-full justify-start")

        # ---------------- painéis
        with ui.tab_panels(tabs, value=tabs.value).classes("w-full bg-transparent"):
            with ui.tab_panel("hub").classes("p-0"):
                views["hub"] = DataHubView(db, on_data_changed)
                views["hub"].build()
            with ui.tab_panel("analise").classes("p-0"):
                views["analytics"] = AnalyticsView(db, state, save_state)
                views["analytics"].build()
            with ui.tab_panel("filtros").classes("p-0"):
                views["qb"] = QueryBuilderView(db, state, save_state, apply_to_analysis, apply_preset)
                views["qb"].build()
            with ui.tab_panel("auditoria").classes("p-0"):
                views["audit"] = AuditView(db, state)
                views["audit"].build()

        def after_snapshot() -> None:
            views["qb"].refresh_library()
            refresh_drawer()

        views["analytics"].on_snapshot_saved = after_snapshot
        refresh_drawer()
        ui.timer(0.1, views["analytics"].refresh, once=True)

    ui.run(title="Consolidação Fiscal SPED", host=config.UI_HOST, port=config.UI_PORT, reload=False,
           native=native, window_size=(1600, 960) if native else None, show=not native, dark=None,
           language="pt-BR", favicon="📊", show_welcome_message=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Consolidação Fiscal SPED (local)")
    ap.add_argument("--browser", action="store_true", help="abrir no navegador em vez de janela nativa")
    ap.add_argument("--importar", nargs="+", metavar="CAMINHO", help="importar pastas/arquivos e sair")
    ap.add_argument("--reconsolidar", action="store_true", help="reconstruir a tabela fato e sair")
    ap.add_argument("--demo", action="store_true", help="gerar e importar arquivos de exemplo")
    args = ap.parse_args()
    config.ensure_dirs()

    if args.demo:
        from tests.sample_data import write_scenario
        dest = config.DATA_DIR / "exemplo_sped"
        write_scenario(dest)
        _cli_import([str(dest)])
    if args.importar:
        _cli_import(args.importar)
    if args.reconsolidar:
        from app.database.engine import get_db
        r = get_db().rebuild_fato(None)
        print(f"{r['linhas']} linhas consolidadas em {r['segundos']:.1f}s")
    if args.importar or args.reconsolidar:
        return

    native = False
    if not args.browser:
        try:
            import webview  # noqa: F401  # type: ignore
            native = True
        except ImportError:
            native = False
    build_ui(native)


if __name__ == "__main__":
    main()
