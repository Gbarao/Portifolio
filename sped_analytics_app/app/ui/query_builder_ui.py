"""Módulo 3 — Construtor de Filtros Sob Demanda (Query Builder), Biblioteca de Filtros Salvos e Snapshots."""
from __future__ import annotations

import copy
import uuid

from nicegui import run, ui

from app import config
from app.database import filter_builder as fb
from app.database import snapshots
from app.database.engine import SpedDatabase
from app.exporter import excel_writer
from app.ui.common import AppState, grid_options, stamp

FIELD_OPTS = {k: f"{v[0]}  [{k}]" for k, v in sorted(fb.FIELDS.items(), key=lambda kv: kv[1][0])}


def _new_rule() -> dict:
    return {"id": uuid.uuid4().hex[:8], "field": "cst_pis", "operator": "em", "value": ""}


def _new_group(op: str = "OR") -> dict:
    return {"id": uuid.uuid4().hex[:8], "op": op, "rules": [_new_rule()]}


def _strip_ids(node: dict) -> dict:
    if "field" in node:
        return {k: node[k] for k in ("field", "operator", "value")}
    return {"op": node.get("op", "AND"), "rules": [_strip_ids(r) for r in node.get("rules", [])]}


def _add_ids(node: dict) -> dict:
    node = copy.deepcopy(node or {"op": "AND", "rules": []})
    node["id"] = uuid.uuid4().hex[:8]
    if "rules" in node:
        node["rules"] = [_add_ids(r) for r in node["rules"]]
    return node


class QueryBuilderView:
    def __init__(self, db: SpedDatabase, state: AppState, save_state, apply_to_analysis, apply_preset):
        self.db = db
        self.state = state
        self.save_state = save_state
        self.apply_to_analysis = apply_to_analysis
        self.apply_preset = apply_preset
        self.tree = _add_ids(state.rules)

    def build(self) -> None:
        with ui.row().classes("w-full gap-4 items-start no-wrap max-lg:flex-wrap"):
            with ui.card().classes("flex-[3] min-w-[640px]"):
                with ui.row().classes("w-full items-center"):
                    ui.label("Criador de Regras em Tempo Real").classes("text-lg font-semibold")
                    ui.space()
                    ui.button("Nova regra em branco", icon="restart_alt", on_click=self._reset).props("flat")
                ui.label("Combine condições sobre qualquer coluna da base consolidada com E / OU. Valores de lista: "
                         "separe por vírgula ou ponto-e-vírgula. 'entre' usa a;b.").classes("text-sm opacity-70")
                self.editor = ui.column().classes("w-full gap-2")
                self._render_editor()
                ui.separator()
                self.preview = ui.label("").classes("text-sm font-mono break-all")
                with ui.row().classes("gap-2 items-center"):
                    ui.button("Testar (contar linhas)", icon="calculate", on_click=self._test).props("outline")
                    ui.button("Aplicar na Análise", icon="play_arrow", on_click=self._apply)
                    ui.button("Salvar filtro atual", icon="bookmark_add", on_click=self._save_dialog).props("outline")
                    self.count_label = ui.label("")
            with ui.column().classes("flex-[2] min-w-[380px] gap-4"):
                with ui.card().classes("w-full"):
                    ui.label("Meus Filtros Salvos").classes("text-lg font-semibold")
                    self.lib = ui.column().classes("w-full gap-1")
                with ui.card().classes("w-full"):
                    ui.label("Análises Congeladas (Snapshots)").classes("text-lg font-semibold")
                    self.snaps = ui.column().classes("w-full gap-1")
        self.refresh_library()
        self._update_preview()

    # ------------------------------------------------------------------ editor
    def _render_editor(self) -> None:
        self.editor.clear()
        with self.editor:
            self._render_group(self.tree, parent=None, depth=0)

    def _render_group(self, g: dict, parent: dict | None, depth: int) -> None:
        bg = "bg-blue-50 dark:bg-slate-800" if depth else ""
        with ui.column().classes(f"w-full gap-1 p-2 rounded border border-dashed {bg}"):
            with ui.row().classes("items-center gap-2"):
                ui.label("Grupo" if depth else "Regras").classes("text-sm font-semibold")
                ui.toggle({"AND": "E (todas)", "OR": "OU (qualquer)"}, value=g.get("op", "AND"),
                          on_change=lambda e, g=g: self._set(g, "op", e.value)).props("dense")
                ui.button("Condição", icon="add", on_click=lambda g=g: self._add(g, _new_rule())).props("flat dense")
                if depth < 2:
                    ui.button("Grupo", icon="library_add", on_click=lambda g=g: self._add(g, _new_group())).props(
                        "flat dense")
                if parent is not None:
                    ui.button(icon="delete", on_click=lambda g=g, p=parent: self._remove(p, g)).props(
                        "flat dense round color=negative")
            for r in g.get("rules", []):
                if "field" in r:
                    self._render_rule(r, g)
                else:
                    self._render_group(r, g, depth + 1)

    def _render_rule(self, r: dict, parent: dict) -> None:
        ftype = fb.FIELDS.get(r["field"], ("", "text"))[1]
        ops = {o: fb.OPERATORS[o] for o in fb.OPS_BY_TYPE[ftype]}
        if r["operator"] not in ops:
            r["operator"] = next(iter(ops))
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.select(FIELD_OPTS, value=r["field"], with_input=True,
                      on_change=lambda e, r=r: self._set(r, "field", e.value, rerender=True)).classes(
                "min-w-[260px]").props("dense options-dense")
            ui.select(ops, value=r["operator"], on_change=lambda e, r=r: self._set(r, "operator", e.value)).classes(
                "w-48").props("dense")
            if r["operator"] not in ("vazio", "preenchido"):
                val = r.get("value")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                ui.input(value="" if val is None else str(val), placeholder="valor",
                         on_change=lambda e, r=r: self._set(r, "value", e.value)).classes("flex-1").props("dense")
            ui.button(icon="close", on_click=lambda r=r, p=parent: self._remove(p, r)).props(
                "flat dense round color=negative")

    def _set(self, node: dict, key: str, value, rerender: bool = False) -> None:
        node[key] = value
        if rerender:
            self._render_editor()
        self._update_preview()

    def _add(self, g: dict, node: dict) -> None:
        g.setdefault("rules", []).append(node)
        self._render_editor()
        self._update_preview()

    def _remove(self, parent: dict, node: dict) -> None:
        parent["rules"] = [x for x in parent.get("rules", []) if x is not node]
        self._render_editor()
        self._update_preview()

    def _reset(self) -> None:
        self.tree = {"id": "root", "op": "AND", "rules": []}
        self._render_editor()
        self._update_preview()

    def load_rules(self, rules: dict) -> None:
        self.tree = _add_ids(rules)
        self._render_editor()
        self._update_preview()

    def current_rules(self) -> dict:
        return _strip_ids(self.tree)

    def _update_preview(self) -> None:
        rules = self.current_rules()
        params: list = []
        try:
            sql = fb.rules_to_sql(rules, params)
            txt = fb.describe_rules(rules) or "(sem regras)"
            self.preview.text = f"{txt}\nSQL: WHERE {sql}  |  parâmetros: {params}"
            self.preview.classes(remove="text-negative")
        except fb.FilterError as e:
            self.preview.text = f"Regra incompleta/inválida: {e}"
            self.preview.classes(add="text-negative")

    async def _test(self) -> None:
        rules = self.current_rules()
        params: list = []
        try:
            where = fb.where_clause(self.state.global_filters, rules, params)
        except fb.FilterError as e:
            ui.notify(str(e), type="negative")
            return
        n = await run.io_bound(self.db.scalar, f"SELECT count(*) FROM {fb.FATO} WHERE {where}", params)
        v = await run.io_bound(self.db.scalar, f"SELECT CAST(sum(vl_contabil) AS DOUBLE) FROM {fb.FATO} WHERE {where}",
                               params)
        self.count_label.text = (f"{n:,} linha(s) — valor contábil R$ {v or 0:,.2f} (com filtros globais atuais)"
                                 ).replace(",", "X").replace(".", ",").replace("X", ".")

    async def _apply(self) -> None:
        rules = self.current_rules()
        try:
            fb.rules_to_sql(rules, [])
        except fb.FilterError as e:
            ui.notify(str(e), type="negative")
            return
        self.state.rules = rules
        self.state.applied_filter_name = ""
        self.save_state()
        await self.apply_to_analysis()

    # ------------------------------------------------------------------ biblioteca
    def _save_dialog(self) -> None:
        cats = sorted({f["categoria"] for f in fb.list_filters(self.db)} | {"Geral", "PIS/COFINS", "ICMS", "Auditoria"})
        with ui.dialog() as d, ui.card().classes("min-w-[480px]"):
            ui.label("Salvar filtro atual").classes("text-lg font-semibold")
            nome = ui.input("Nome do filtro").classes("w-full")
            cat = ui.select(cats, value="Geral", label="Categoria", with_input=True, new_value_mode="add-unique"
                            ).classes("w-full")
            inc_global = ui.checkbox("Incluir filtros globais atuais (período, filiais, fornecedores...)", value=True)
            inc_view = ui.checkbox("Incluir hierarquia/modo de visualização", value=True)

            def salvar() -> None:
                if not (nome.value or "").strip():
                    ui.notify("Informe um nome", type="warning")
                    return
                definicao = {"rules": self.current_rules(),
                             "global": self.state.global_filters if inc_global.value else {}}
                if inc_view.value:
                    definicao["view"] = {"hierarchy": self.state.hierarchy, "mode": self.state.mode,
                                         "metrics": self.state.metrics}
                try:
                    fb.save_filter(self.db, nome.value.strip(), cat.value or "Geral", definicao)
                except fb.FilterError as e:
                    ui.notify(str(e), type="negative")
                    return
                d.close()
                ui.notify("Filtro salvo", type="positive")
                self.refresh_library()

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancelar", on_click=d.close).props("flat")
                ui.button("Salvar", icon="save", on_click=salvar)
        d.open()

    def refresh_library(self) -> None:
        self.lib.clear()
        filtros = fb.list_filters(self.db)
        with self.lib:
            if not filtros:
                ui.label("Nenhum filtro salvo.").classes("text-sm opacity-60")
            cat = None
            for f in filtros:
                if f["categoria"] != cat:
                    cat = f["categoria"]
                    ui.label(cat).classes("text-xs uppercase opacity-60 mt-2")
                with ui.row().classes("w-full items-center no-wrap gap-1"):
                    ui.button(f["nome"], icon="bolt", on_click=lambda f=f: self.apply_preset(f)).props(
                        "flat dense no-caps align=left").classes("flex-1 justify-start")
                    ui.button(icon="edit", on_click=lambda f=f: self.load_rules(f["definicao"].get("rules") or {})
                              ).props("flat dense round").tooltip("Carregar no editor")
                    ui.button(icon="delete", on_click=lambda f=f: self._delete_filter(f)).props(
                        "flat dense round color=negative")
        self.snaps.clear()
        with self.snaps:
            snaps = snapshots.list_snapshots(self.db)
            if not snaps:
                ui.label("Nenhum snapshot.").classes("text-sm opacity-60")
            for s in snaps:
                with ui.row().classes("w-full items-center no-wrap gap-1"):
                    ui.button(f"#{s['id']} {s['nome']}", icon="ac_unit", on_click=lambda s=s: self.open_snapshot(s["id"])
                              ).props("flat dense no-caps align=left").classes("flex-1 justify-start")
                    ui.label(f"{s['criado_em']} · {s['linhas']} lin.").classes("text-xs opacity-60")

    def _delete_filter(self, f: dict) -> None:
        fb.delete_filter(self.db, f["id"])
        self.refresh_library()
        ui.notify(f"Filtro '{f['nome']}' excluído")

    def open_snapshot(self, sid: int) -> None:
        meta, df, ok = snapshots.load_snapshot(self.db, sid)
        with ui.dialog().props("maximized") as d, ui.card().classes("w-full h-full"):
            with ui.row().classes("w-full items-center"):
                ui.label(f"Snapshot #{meta['id']} — {meta['nome']}").classes("text-lg font-semibold")
                ui.badge("Íntegro" if ok else "INTEGRIDADE VIOLADA", color="positive" if ok else "negative")
                ui.space()

                async def export() -> None:
                    p = config.DATA_DIR / "exports" / f"snapshot_{sid}_{stamp()}.xlsx"
                    ctx = {k: v for k, v in meta["contexto"].items() if k != "state"}
                    await run.io_bound(excel_writer.export_frames_excel, p, {"Snapshot": df},
                                       {"Snapshot": meta["nome"], "Criado em": meta["criado_em"],
                                        "Anotações": meta["anotacoes"], **ctx})
                    ui.download(p)

                def excluir() -> None:
                    snapshots.delete_snapshot(self.db, sid)
                    d.close()
                    self.refresh_library()

                ui.button("Exportar Excel", icon="download", on_click=export).props("flat")
                ui.button("Restaurar contexto na Análise", icon="history",
                          on_click=lambda: (d.close(), self.apply_preset(
                              {"nome": f"Snapshot #{sid}", "definicao": {
                                  "rules": meta["contexto"].get("state", {}).get("rules"),
                                  "global": meta["contexto"].get("state", {}).get("global_filters", {}),
                                  "view": {k: meta["contexto"].get("state", {}).get(k) for k in
                                           ("hierarchy", "mode", "metrics")}}}))).props("flat")
                ui.button("Excluir", icon="delete", color="negative", on_click=excluir).props("flat")
                ui.button(icon="close", on_click=d.close).props("flat round")
            ui.label(f"Criado em {meta['criado_em']}").classes("text-sm opacity-70")
            if meta["anotacoes"]:
                ui.markdown(meta["anotacoes"]).classes("text-sm")
            ctx = {k: v for k, v in meta["contexto"].items() if k != "state"}
            ui.label(" | ".join(f"{k}: {v}" for k, v in ctx.items() if v)).classes("text-xs opacity-70")
            ui.aggrid(grid_options(df, pin_first=2), auto_size_columns=False).classes("w-full").style(
                "height: calc(100vh - 200px)")
        d.open()
