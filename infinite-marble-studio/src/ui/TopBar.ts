import { button, el } from './dom';

export interface TopBarActions {
  togglePlay(): void;
  restart(): void;
  randomizeAll(): void;
  randomizePath(): void;
  randomizeAppearance(): void;
  newVariation(): void;
  undo(): void;
  redo(): void;
  toggleHelpers(): void;
  toggleGui(): void;
  toggleEditorView(): void;
  showShortcuts(): void;
}

/** Barra superior com as ações principais (alvos de toque ≥ 44 px). */
export class TopBar {
  private readonly playButton: HTMLButtonElement;
  private readonly undoButton: HTMLButtonElement;
  private readonly redoButton: HTMLButtonElement;
  private readonly helpersButton: HTMLButtonElement;
  private readonly guiButton: HTMLButtonElement;
  private readonly editorButton: HTMLButtonElement;

  constructor(container: HTMLElement, actions: TopBarActions) {
    const brand = el('div', { className: 'brand' }, [
      el('span', { className: 'brand-mark', 'aria-hidden': 'true' }, ['◉']),
      el('span', { className: 'brand-name' }, ['Infinite Marble Studio']),
    ]);
    this.playButton = button(
      '⏸ Pausar',
      'Play/Pause (Espaço)',
      actions.togglePlay,
      'btn btn-primary',
    );
    this.undoButton = button('↶ Desfazer', 'Desfazer (Ctrl+Z)', actions.undo);
    this.redoButton = button('↷ Refazer', 'Refazer (Ctrl+Shift+Z)', actions.redo);
    this.helpersButton = button(
      'Helpers',
      'Mostrar/Esconder helpers de edição (H)',
      actions.toggleHelpers,
    );
    this.guiButton = button(
      'Painel',
      'Mostrar/Esconder painel de controles (G)',
      actions.toggleGui,
    );
    this.editorButton = button(
      'Vista livre',
      'Vista de edição livre (V)',
      actions.toggleEditorView,
    );

    const groups = [
      [this.playButton, button('⟲ Reiniciar', 'Reiniciar (R)', actions.restart)],
      [
        button('🎲 Tudo', 'Randomizar tudo (T)', actions.randomizeAll),
        button('Trajeto', 'Randomizar trajeto (Shift+T)', actions.randomizePath),
        button('Aparência', 'Randomizar aparência (Shift+A)', actions.randomizeAppearance),
        button('✦ Variação', 'Nova variação: altera 3+ categorias (N)', actions.newVariation),
      ],
      [this.undoButton, this.redoButton],
      [
        this.helpersButton,
        this.editorButton,
        this.guiButton,
        button('?', 'Atalhos de teclado (?)', actions.showShortcuts, 'btn btn-icon'),
      ],
    ];
    container.append(brand, ...groups.map((items) => el('div', { className: 'btn-group' }, items)));
  }

  update(state: {
    playing: boolean;
    canUndo: boolean;
    canRedo: boolean;
    helpersVisible: boolean;
    guiVisible: boolean;
    editorView: boolean;
  }): void {
    this.playButton.textContent = state.playing ? '⏸ Pausar' : '▶ Play';
    this.undoButton.disabled = !state.canUndo;
    this.redoButton.disabled = !state.canRedo;
    this.helpersButton.setAttribute('aria-pressed', String(state.helpersVisible));
    this.guiButton.setAttribute('aria-pressed', String(state.guiVisible));
    this.editorButton.setAttribute('aria-pressed', String(state.editorView));
  }
}
