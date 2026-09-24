import type { CaptureHost } from './CaptureHost';
import { canvasToBlob, createThumbnail } from './DownloadUtils';

export interface ImageExportResult {
  blob: Blob;
  thumbnail: string;
  width: number;
  height: number;
}

/** Captura um PNG na resolução final, com GUI e helpers ocultos. */
export class ImageExporter {
  constructor(private readonly host: CaptureHost) {}

  async capture(normalizedTime: number, exportFps: number): Promise<ImageExportResult> {
    this.host.beginCapture(exportFps);
    try {
      this.host.renderNormalizedTime(normalizedTime);
      // Leitura na mesma tarefa da renderização (drawing buffer ainda válido).
      const blobPromise = canvasToBlob(this.host.canvas, 'image/png');
      const thumbnail = createThumbnail(this.host.canvas);
      const width = this.host.canvas.width;
      const height = this.host.canvas.height;
      const blob = await blobPromise;
      return { blob, thumbnail, width, height };
    } finally {
      this.host.endCapture();
    }
  }
}
