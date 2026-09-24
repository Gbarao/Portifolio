/** Contrato entre os exportadores e a aplicação (implementado por App). */
export interface CaptureHost {
  readonly canvas: HTMLCanvasElement;
  /** Oculta GUI/helpers, muda para a resolução final e coloca o relógio em modo export. */
  beginCapture(exportFps: number): void;
  /** Restaura preview, GUI e helpers. */
  endCapture(): void;
  /** Renderiza o frame `frameIndex` do vídeo (tempo normalizado = frame / framesPerLoop). */
  renderExportFrame(frameIndex: number): void;
  /** Renderiza um tempo normalizado arbitrário na resolução de captura. */
  renderNormalizedTime(normalizedTime: number): void;
  /** Verdadeiro se helpers e GUI estão ocultos (verificação do checklist). */
  isCaptureClean(): { helpersHidden: boolean; guiHidden: boolean };
}
