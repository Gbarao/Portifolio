import { PCFShadowMap, WebGLRenderer } from 'three';
import type { Disposable } from '../core/Disposable';

export interface ViewportLayout {
  cssWidth: number;
  cssHeight: number;
  bufferWidth: number;
  bufferHeight: number;
}

/**
 * Encapsula o WebGLRenderer e separa resolução de visualização (adaptada à janela) da
 * resolução de exportação (usada apenas durante capturas).
 */
export class RendererManager implements Disposable {
  readonly renderer: WebGLRenderer;
  readonly canvas: HTMLCanvasElement;
  private outputWidth = 1080;
  private outputHeight = 1920;
  private capturing = false;
  private readonly resizeObserver: ResizeObserver;
  /** Limite de devicePixelRatio no preview (1 a 2). */
  maxPixelRatio = 1;
  /** Renderiza o preview já na resolução de exportação (reduzido via CSS). */
  previewAtExportResolution = false;
  onLayout: ((layout: ViewportLayout) => void) | null = null;

  constructor(private readonly container: HTMLElement) {
    this.renderer = new WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: false,
      powerPreference: 'high-performance',
    });
    this.renderer.shadowMap.type = PCFShadowMap;
    this.canvas = this.renderer.domElement;
    this.canvas.id = 'scene-canvas';
    this.canvas.setAttribute('aria-label', 'Visualização 3D da animação');
    this.canvas.tabIndex = 0;
    container.appendChild(this.canvas);
    this.resizeObserver = new ResizeObserver(() => this.layout());
    this.resizeObserver.observe(container);
    this.layout();
  }

  get isCapturing(): boolean {
    return this.capturing;
  }

  get aspect(): number {
    return this.outputWidth / this.outputHeight;
  }

  get outputSize(): { width: number; height: number } {
    return { width: this.outputWidth, height: this.outputHeight };
  }

  setOutputSize(width: number, height: number): void {
    this.outputWidth = width;
    this.outputHeight = height;
    this.layout();
  }

  /** Ajusta o canvas à área disponível mantendo a proporção de saída (letterbox). */
  layout(): ViewportLayout {
    const rect = this.container.getBoundingClientRect();
    const availableW = Math.max(1, rect.width - 16);
    const availableH = Math.max(1, rect.height - 16);
    const aspect = this.aspect;
    let cssWidth = availableW;
    let cssHeight = availableW / aspect;
    if (cssHeight > availableH) {
      cssHeight = availableH;
      cssWidth = availableH * aspect;
    }
    cssWidth = Math.floor(cssWidth);
    cssHeight = Math.floor(cssHeight);
    this.canvas.style.width = `${cssWidth}px`;
    this.canvas.style.height = `${cssHeight}px`;

    if (!this.capturing) {
      if (this.previewAtExportResolution) {
        this.renderer.setPixelRatio(1);
        this.renderer.setSize(this.outputWidth, this.outputHeight, false);
      } else {
        const ratio = Math.min(globalThis.devicePixelRatio || 1, this.maxPixelRatio);
        this.renderer.setPixelRatio(ratio);
        this.renderer.setSize(cssWidth, cssHeight, false);
      }
    }
    const layout: ViewportLayout = {
      cssWidth,
      cssHeight,
      bufferWidth: this.canvas.width,
      bufferHeight: this.canvas.height,
    };
    this.onLayout?.(layout);
    return layout;
  }

  /** Muda o drawing buffer para a resolução final de exportação. */
  beginCapture(): void {
    this.capturing = true;
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(this.outputWidth, this.outputHeight, false);
  }

  /** Restaura a resolução de preview. */
  endCapture(): void {
    this.capturing = false;
    this.layout();
  }

  dispose(): void {
    this.resizeObserver.disconnect();
    this.renderer.dispose();
    this.canvas.remove();
  }
}
