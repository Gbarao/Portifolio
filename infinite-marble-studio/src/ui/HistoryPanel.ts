import type { ExportHistoryEntry } from '../export/ExportHistory';
import { button, el } from './dom';

export interface HistoryPanelActions {
  redownload(entry: ExportHistoryEntry): void;
  remove(entry: ExportHistoryEntry): void;
}

const KIND_LABEL: Record<ExportHistoryEntry['kind'], string> = {
  video: 'WebM',
  zip: 'ZIP (PNG)',
  image: 'PNG',
};

/** Lista das últimas exportações (metadados + miniatura). */
export class HistoryPanel {
  readonly element = el('div', {
    className: 'history-list',
    'aria-label': 'Histórico de exportações',
  });

  constructor(private readonly actions: HistoryPanelActions) {}

  render(entries: readonly ExportHistoryEntry[]): void {
    if (entries.length === 0) {
      this.element.replaceChildren(el('p', { className: 'hint' }, ['Nenhuma exportação ainda.']));
      return;
    }
    this.element.replaceChildren(
      ...entries.map((entry) => {
        const date = new Date(entry.createdAt).toLocaleString('pt-BR');
        const meta =
          entry.kind === 'image'
            ? `${entry.width}×${entry.height}`
            : `${entry.width}×${entry.height} · ${entry.durationSeconds}s · ${entry.fps} fps`;
        const thumb = entry.thumbnail
          ? el('img', {
              src: entry.thumbnail,
              alt: `Miniatura de ${entry.fileName}`,
              className: 'history-thumb',
            })
          : el('div', { className: 'history-thumb history-thumb-empty', 'aria-hidden': 'true' });
        return el('div', { className: 'history-item' }, [
          thumb,
          el('div', { className: 'history-info' }, [
            el('div', { className: 'history-name', title: entry.fileName }, [entry.fileName]),
            el('div', { className: 'history-meta' }, [`${KIND_LABEL[entry.kind]} · ${meta}`]),
            el('div', { className: 'history-meta' }, [
              `${date} · seed ${entry.seed} · ${entry.presetName}`,
            ]),
            el('div', { className: 'history-actions' }, [
              button(
                'Re-download',
                'Baixar novamente (re-renderiza se necessário)',
                () => this.actions.redownload(entry),
                'btn btn-small',
              ),
              button(
                'Deletar',
                'Remover do histórico',
                () => this.actions.remove(entry),
                'btn btn-small btn-danger',
              ),
            ]),
          ]),
        ]);
      }),
    );
  }
}
