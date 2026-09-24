export type ShortcutAction =
  | 'togglePlay'
  | 'restart'
  | 'randomizeAll'
  | 'randomizePath'
  | 'randomizeAppearance'
  | 'newVariation'
  | 'undo'
  | 'redo'
  | 'savePreset'
  | 'exportVideo'
  | 'toggleHelpers'
  | 'toggleGui'
  | 'toggleEditorView'
  | 'showShortcuts'
  | 'deletePoint'
  | 'duplicatePoint'
  | 'escape';

export interface ShortcutDefinition {
  action: ShortcutAction;
  keys: string;
  description: string;
  matches: (event: KeyboardEvent) => boolean;
}

const plain = (event: KeyboardEvent): boolean => !event.ctrlKey && !event.metaKey && !event.altKey;
const ctrl = (event: KeyboardEvent): boolean => (event.ctrlKey || event.metaKey) && !event.altKey;

/** Tabela única de atalhos: usada pelo handler, pelo diálogo "?" e pela documentação. */
export const SHORTCUTS: readonly ShortcutDefinition[] = [
  {
    action: 'togglePlay',
    keys: 'Space',
    description: 'Play/Pause',
    matches: (e) => plain(e) && e.code === 'Space',
  },
  {
    action: 'restart',
    keys: 'R',
    description: 'Reiniciar',
    matches: (e) => plain(e) && !e.shiftKey && e.code === 'KeyR',
  },
  {
    action: 'randomizeAll',
    keys: 'T',
    description: 'Randomizar tudo',
    matches: (e) => plain(e) && !e.shiftKey && e.code === 'KeyT',
  },
  {
    action: 'randomizePath',
    keys: 'Shift+T',
    description: 'Randomizar trajeto',
    matches: (e) => plain(e) && e.shiftKey && e.code === 'KeyT',
  },
  {
    action: 'randomizeAppearance',
    keys: 'Shift+A',
    description: 'Randomizar aparência',
    matches: (e) => plain(e) && e.shiftKey && e.code === 'KeyA',
  },
  {
    action: 'newVariation',
    keys: 'N',
    description: 'Nova variação (3+ categorias)',
    matches: (e) => plain(e) && !e.shiftKey && e.code === 'KeyN',
  },
  {
    action: 'undo',
    keys: 'Ctrl+Z',
    description: 'Desfazer',
    matches: (e) => ctrl(e) && !e.shiftKey && e.code === 'KeyZ',
  },
  {
    action: 'redo',
    keys: 'Ctrl+Shift+Z',
    description: 'Refazer (também Ctrl+Y)',
    matches: (e) => ctrl(e) && ((e.shiftKey && e.code === 'KeyZ') || e.code === 'KeyY'),
  },
  {
    action: 'savePreset',
    keys: 'Ctrl+S',
    description: 'Salvar preset',
    matches: (e) => ctrl(e) && e.code === 'KeyS',
  },
  {
    action: 'exportVideo',
    keys: 'Ctrl+E',
    description: 'Exportar vídeo',
    matches: (e) => ctrl(e) && e.code === 'KeyE',
  },
  {
    action: 'toggleHelpers',
    keys: 'H',
    description: 'Mostrar/Esconder helpers',
    matches: (e) => plain(e) && !e.shiftKey && e.code === 'KeyH',
  },
  {
    action: 'toggleGui',
    keys: 'G',
    description: 'Mostrar/Esconder GUI',
    matches: (e) => plain(e) && !e.shiftKey && e.code === 'KeyG',
  },
  {
    action: 'toggleEditorView',
    keys: 'V',
    description: 'Vista de edição livre',
    matches: (e) => plain(e) && !e.shiftKey && e.code === 'KeyV',
  },
  {
    action: 'showShortcuts',
    keys: '?',
    description: 'Mostrar atalhos',
    matches: (e) => !e.ctrlKey && !e.metaKey && e.key === '?',
  },
  {
    action: 'deletePoint',
    keys: 'Delete',
    description: 'Deletar ponto selecionado',
    matches: (e) => plain(e) && e.key === 'Delete',
  },
  {
    action: 'duplicatePoint',
    keys: 'Ctrl+D',
    description: 'Duplicar ponto selecionado',
    matches: (e) => ctrl(e) && e.code === 'KeyD',
  },
  {
    action: 'escape',
    keys: 'Esc',
    description: 'Desmarcar ponto / fechar diálogos',
    matches: (e) => e.key === 'Escape',
  },
];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return true;
  if (target instanceof HTMLInputElement) {
    return !['checkbox', 'radio', 'button', 'range', 'color'].includes(target.type);
  }
  return false;
}

/** Registra os atalhos no documento. Ignora teclas digitadas em campos de texto. */
export function installKeyboardShortcuts(
  handlers: Partial<Record<ShortcutAction, () => void>>,
  isBlocked: () => boolean,
): () => void {
  const listener = (event: KeyboardEvent): void => {
    const shortcut = SHORTCUTS.find((s) => s.matches(event));
    if (!shortcut) return;
    // Em campos de texto só valem Esc, Ctrl+S e Ctrl+E (o campo mantém seu próprio desfazer).
    const allowedWhileTyping = ['escape', 'savePreset', 'exportVideo'].includes(shortcut.action);
    if (isTypingTarget(event.target) && !allowedWhileTyping) return;
    const repeatable = shortcut.action === 'undo' || shortcut.action === 'redo';
    if ((event.repeat && !repeatable) || (isBlocked() && shortcut.action !== 'escape')) {
      event.preventDefault();
      return;
    }
    const handler = handlers[shortcut.action];
    if (!handler) return;
    event.preventDefault();
    handler();
  };
  document.addEventListener('keydown', listener);
  return () => document.removeEventListener('keydown', listener);
}
