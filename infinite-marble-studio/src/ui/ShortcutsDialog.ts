import { button, el } from './dom';
import { SHORTCUTS } from './KeyboardShortcuts';

/** Diálogo com a lista de atalhos (tecla "?"). */
export class ShortcutsDialog {
  constructor(private readonly dialog: HTMLDialogElement) {
    const rows = SHORTCUTS.map((s) =>
      el('tr', {}, [el('td', {}, [el('kbd', {}, [s.keys])]), el('td', {}, [s.description])]),
    );
    dialog.setAttribute('aria-labelledby', 'shortcuts-title');
    dialog.append(
      el('h2', { id: 'shortcuts-title' }, ['Atalhos de teclado']),
      el('table', { className: 'shortcuts-table' }, [el('tbody', {}, rows)]),
      el('p', { className: 'hint' }, [
        'Arraste um arquivo .json para qualquer lugar da janela para carregar um preset.',
      ]),
      button('Fechar', 'Fechar atalhos', () => this.close(), 'btn btn-primary'),
    );
  }

  get isOpen(): boolean {
    return this.dialog.open;
  }

  toggle(): void {
    if (this.dialog.open) this.close();
    else this.dialog.showModal();
  }

  close(): void {
    if (this.dialog.open) this.dialog.close();
  }
}
