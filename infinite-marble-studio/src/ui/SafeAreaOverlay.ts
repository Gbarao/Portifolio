import { el } from './dom';

export const SAFE_AREA_MARGIN = 0.2;

/** Guia de área segura para textos: 20% de margem em cada borda (oculto nas capturas). */
export class SafeAreaOverlay {
  private readonly inner = el('div', { className: 'safe-area-inner' }, [
    el('span', { className: 'safe-area-label' }, ['Área segura (20%)']),
  ]);

  constructor(
    private readonly overlay: HTMLElement,
    private readonly canvas: HTMLCanvasElement,
  ) {
    overlay.append(this.inner);
    const pct = `${SAFE_AREA_MARGIN * 100}%`;
    Object.assign(this.inner.style, { left: pct, right: pct, top: pct, bottom: pct });
  }

  setVisible(visible: boolean): void {
    this.overlay.hidden = !visible;
    if (visible) this.sync();
  }

  /** Alinha a sobreposição ao retângulo do canvas. */
  sync(): void {
    Object.assign(this.overlay.style, {
      left: `${this.canvas.offsetLeft}px`,
      top: `${this.canvas.offsetTop}px`,
      width: `${this.canvas.offsetWidth}px`,
      height: `${this.canvas.offsetHeight}px`,
    });
  }
}
