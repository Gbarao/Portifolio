import type { ResolutionPresetId } from '../presets/PresetSchema';
import { el } from './dom';

export type SimpleFormat = Exclude<ResolutionPresetId, 'custom'>;

export interface SimpleStyle {
  /** Nome do preset built-in carregado ao escolher o estilo. */
  presetName: string;
  label: string;
  /** Gradiente CSS da miniatura. */
  swatch: string;
}

export const SIMPLE_STYLES: readonly SimpleStyle[] = [
  {
    presetName: 'Wooden Coil',
    label: 'Madeira',
    swatch: 'linear-gradient(160deg, #e39a5b, #9c5a2c)',
  },
  {
    presetName: 'Blue Coaster',
    label: 'Montanha Azul',
    swatch: 'linear-gradient(160deg, #3b86f0, #163f86)',
  },
  {
    presetName: 'Mesmerizing Circle',
    label: 'Círculo Neon',
    swatch: 'radial-gradient(circle at 50% 50%, #3b1a70, #07030f)',
  },
  {
    presetName: 'Golden Spiral',
    label: 'Espiral Dourada',
    swatch: 'linear-gradient(160deg, #6b4a1c, #1a1006)',
  },
  {
    presetName: 'Twisted Figure',
    label: 'Oito Pastel',
    swatch: 'linear-gradient(160deg, #e7a6c8, #8ea3d8)',
  },
  {
    presetName: 'Dark Loop',
    label: 'Nó Neon',
    swatch: 'linear-gradient(160deg, #2a0a4a, #020108)',
  },
  {
    presetName: 'Minimalist',
    label: 'Minimalista',
    swatch: 'linear-gradient(160deg, #e6e6e6, #9a9a9a)',
  },
];

export const SIMPLE_DURATIONS: readonly { seconds: number; label: string }[] = [
  { seconds: 5, label: '5 s' },
  { seconds: 8, label: '8 s' },
  { seconds: 15, label: '15 s' },
  { seconds: 30, label: '30 s' },
  { seconds: 60, label: '1 min' },
];

const FORMATS: readonly { id: SimpleFormat; label: string; hint: string }[] = [
  { id: 'vertical', label: '▯ Vertical', hint: '9:16 · TikTok, Reels, Shorts' },
  { id: 'horizontal', label: '▭ Horizontal', hint: '16:9 · YouTube, X' },
  { id: 'square', label: '□ Quadrado', hint: '1:1 · Feed do Instagram' },
];

export interface SimplePanelActions {
  applyStyle(presetName: string): void;
  surprise(): void;
  setFormat(format: SimpleFormat): void;
  setDuration(seconds: number): void;
  downloadVideo(): void;
  downloadImage(): void;
}

export interface SimplePanelState {
  styleName: string | null;
  format: ResolutionPresetId;
  durationSeconds: number;
  info: string;
}

function choiceButton(
  label: string,
  title: string,
  onClick: () => void,
  className: string,
): HTMLButtonElement {
  const b = el('button', { type: 'button', className, title, 'aria-pressed': 'false' }, [label]);
  b.addEventListener('click', onClick);
  return b;
}

/** Interface simplificada: estilo → formato → duração → baixar. */
export class SimplePanel {
  private readonly styleButtons = new Map<string, HTMLButtonElement>();
  private readonly formatButtons = new Map<SimpleFormat, HTMLButtonElement>();
  private readonly durationButtons = new Map<number, HTMLButtonElement>();
  private readonly info = el('p', { className: 'simple-info', 'aria-live': 'polite' });

  constructor(container: HTMLElement, actions: SimplePanelActions) {
    const step = (number: number, title: string, ...children: HTMLElement[]): HTMLElement =>
      el('section', { className: 'simple-step' }, [
        el('h2', {}, [`${number}. ${title}`]),
        ...children,
      ]);

    const styleGrid = el('div', { className: 'style-grid' });
    for (const style of SIMPLE_STYLES) {
      const card = choiceButton(
        style.label,
        `Usar o estilo ${style.label}`,
        () => actions.applyStyle(style.presetName),
        'style-card',
      );
      card.style.setProperty('--swatch', style.swatch);
      this.styleButtons.set(style.presetName, card);
      styleGrid.append(card);
    }
    const surprise = choiceButton(
      '🎲 Surpreenda-me',
      'Cria uma animação aleatória nova a cada clique',
      () => actions.surprise(),
      'style-card style-card-surprise',
    );
    styleGrid.append(surprise);

    const formatRow = el('div', { className: 'choice-row' });
    for (const format of FORMATS) {
      const b = choiceButton(
        format.label,
        format.hint,
        () => actions.setFormat(format.id),
        'btn choice',
      );
      this.formatButtons.set(format.id, b);
      formatRow.append(b);
    }

    const durationRow = el('div', { className: 'choice-row' });
    for (const { seconds, label } of SIMPLE_DURATIONS) {
      const b = choiceButton(
        label,
        `Vídeo de ${label} em loop perfeito`,
        () => actions.setDuration(seconds),
        'btn choice',
      );
      this.durationButtons.set(seconds, b);
      durationRow.append(b);
    }

    const video = choiceButton(
      '⬇ Baixar vídeo',
      'Grava o loop e salva o vídeo na pasta de downloads',
      () => actions.downloadVideo(),
      'btn btn-primary btn-download',
    );
    video.removeAttribute('aria-pressed');
    const image = choiceButton(
      '📷 Baixar imagem',
      'Salva o quadro atual como imagem PNG',
      () => actions.downloadImage(),
      'btn btn-download-secondary',
    );
    image.removeAttribute('aria-pressed');

    container.append(
      step(1, 'Escolha um estilo', styleGrid),
      step(2, 'Formato', formatRow),
      step(3, 'Duração', durationRow),
      step(4, 'Baixar', video, image, this.info),
    );
  }

  update(state: SimplePanelState): void {
    for (const [name, b] of this.styleButtons) {
      b.setAttribute('aria-pressed', String(name === state.styleName));
    }
    for (const [id, b] of this.formatButtons) {
      b.setAttribute('aria-pressed', String(id === state.format));
    }
    for (const [seconds, b] of this.durationButtons) {
      b.setAttribute('aria-pressed', String(seconds === state.durationSeconds));
    }
    this.info.textContent = state.info;
  }
}
