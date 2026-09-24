import type { VideoCodec } from '../presets/PresetSchema';
import type { CaptureHost } from './CaptureHost';
import { canvasToBlob, createThumbnail } from './DownloadUtils';
import { ZipWriter } from './ZipWriter';

export interface VideoExportOptions {
  fps: number;
  totalFrames: number;
  bitrateMbps: number;
  codec: VideoCodec;
  /** JSON do preset incluído no ZIP de fallback. */
  presetJson: string;
}

export interface VideoExportProgress {
  frame: number;
  totalFrames: number;
  percent: number;
  elapsedMs: number;
  estimatedTotalMs: number;
  /** Atraso acumulado em relação ao tempo real (ms). */
  lagMs: number;
  paused: boolean;
}

export interface VideoExportResult {
  kind: 'webm' | 'zip';
  blob: Blob;
  mimeType: string;
  thumbnail: string;
  lagMs: number;
}

export class ExportCancelledError extends Error {
  constructor() {
    super('Exportação cancelada.');
    this.name = 'ExportCancelledError';
  }
}

const MIME_BY_CODEC: Record<VideoCodec, string> = {
  vp8: 'video/webm;codecs=vp8',
  vp9: 'video/webm;codecs=vp9',
};

/** Retorna o mimeType suportado (codec pedido, VP8 como fallback) ou null. */
export function getSupportedMimeType(codec: VideoCodec): string | null {
  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
    return null;
  }
  for (const mime of [MIME_BY_CODEC[codec], MIME_BY_CODEC.vp8, 'video/webm']) {
    if (MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return null;
}

export function isVideoRecordingSupported(canvas: HTMLCanvasElement, codec: VideoCodec): boolean {
  return typeof canvas.captureStream === 'function' && getSupportedMimeType(codec) !== null;
}

const nextAnimationFrame = (): Promise<number> =>
  new Promise((resolve) => requestAnimationFrame(resolve));

/**
 * Exporta o loop frame a frame. Cada frame é renderizado a partir do índice (modo Export
 * do LoopClock) e enviado ao MediaRecorder via captureStream(0) + requestFrame().
 * O ritmo segue o requestAnimationFrame alinhado ao tempo real, porque o MediaRecorder
 * registra cada frame com o horário de captura.
 */
export class VideoExporter {
  constructor(private readonly host: CaptureHost) {}

  async export(
    options: VideoExportOptions,
    onProgress: (progress: VideoExportProgress) => void,
    signal: AbortSignal,
  ): Promise<VideoExportResult> {
    const mimeType = getSupportedMimeType(options.codec);
    this.host.beginCapture(options.fps);
    try {
      if (mimeType && typeof this.host.canvas.captureStream === 'function') {
        return await this.recordWebm(options, mimeType, onProgress, signal);
      }
      return await this.recordPngZip(options, onProgress, signal);
    } finally {
      this.host.endCapture();
    }
  }

  private async recordWebm(
    options: VideoExportOptions,
    mimeType: string,
    onProgress: (progress: VideoExportProgress) => void,
    signal: AbortSignal,
  ): Promise<VideoExportResult> {
    const { fps, totalFrames } = options;
    const stream = this.host.canvas.captureStream(0);
    const track = stream.getVideoTracks()[0] as CanvasCaptureMediaStreamTrack | undefined;
    if (!track) throw new Error('Não foi possível capturar o canvas (captureStream).');
    const recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: Math.round(options.bitrateMbps * 1_000_000),
    });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    const stopped = new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
    });

    const frameMs = 1000 / fps;
    let thumbnail = '';
    let hiddenSince: number | null = null;
    const onVisibility = (): void => {
      if (document.hidden && recorder.state === 'recording') {
        recorder.pause();
        hiddenSince = performance.now();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    try {
      recorder.start(1000);
      let schedule = await nextAnimationFrame();
      const startedAt = performance.now();
      let frame = 0;
      let lagMs = 0;
      while (frame < totalFrames) {
        if (signal.aborted) throw new ExportCancelledError();
        const now = await nextAnimationFrame();
        if (hiddenSince !== null) {
          // Aba voltou a ficar visível: retoma e reancora o cronograma.
          if (document.hidden) continue;
          schedule += now - hiddenSince;
          hiddenSince = null;
          recorder.resume();
        }
        const due = schedule + frame * frameMs;
        if (now + 2 < due) continue; // ainda não é hora deste frame
        lagMs = Math.max(lagMs, now - due);
        this.host.renderExportFrame(frame);
        track.requestFrame();
        if (frame === 0) thumbnail = createThumbnail(this.host.canvas);
        frame++;
        const elapsedMs = performance.now() - startedAt;
        onProgress({
          frame,
          totalFrames,
          percent: (frame / totalFrames) * 100,
          elapsedMs,
          estimatedTotalMs: (elapsedMs / frame) * totalFrames,
          lagMs,
          paused: false,
        });
      }
      // Mantém o último frame pela sua duração antes de encerrar.
      const end = schedule + totalFrames * frameMs;
      while ((await nextAnimationFrame()) + 2 < end) {
        if (signal.aborted) throw new ExportCancelledError();
      }
      recorder.stop();
      await stopped;
      return {
        kind: 'webm',
        blob: new Blob(chunks, { type: mimeType }),
        mimeType,
        thumbnail,
        lagMs,
      };
    } catch (error) {
      if (recorder.state !== 'inactive') {
        recorder.stop();
        await stopped;
      }
      throw error;
    } finally {
      document.removeEventListener('visibilitychange', onVisibility);
      stream.getTracks().forEach((t) => t.stop());
    }
  }

  /** Fallback: sequência PNG em ZIP (sem MediaRecorder). */
  private async recordPngZip(
    options: VideoExportOptions,
    onProgress: (progress: VideoExportProgress) => void,
    signal: AbortSignal,
  ): Promise<VideoExportResult> {
    const zip = new ZipWriter();
    const startedAt = performance.now();
    let thumbnail = '';
    const digits = Math.max(5, String(options.totalFrames).length);
    for (let frame = 0; frame < options.totalFrames; frame++) {
      if (signal.aborted) throw new ExportCancelledError();
      this.host.renderExportFrame(frame);
      const blobPromise = canvasToBlob(this.host.canvas, 'image/png');
      if (frame === 0) thumbnail = createThumbnail(this.host.canvas);
      const blob = await blobPromise;
      zip.addFile(
        `frame_${String(frame).padStart(digits, '0')}.png`,
        new Uint8Array(await blob.arrayBuffer()),
      );
      const elapsedMs = performance.now() - startedAt;
      onProgress({
        frame: frame + 1,
        totalFrames: options.totalFrames,
        percent: ((frame + 1) / options.totalFrames) * 100,
        elapsedMs,
        estimatedTotalMs: (elapsedMs / (frame + 1)) * options.totalFrames,
        lagMs: 0,
        paused: false,
      });
    }
    zip.addText('preset.json', options.presetJson);
    zip.addText(
      'LEIA-ME.txt',
      [
        'Sequência PNG gerada pelo Infinite Marble Studio (fallback sem MediaRecorder).',
        'Converter para MP4 (opcional):',
        `ffmpeg -framerate ${options.fps} -i frame_%0${digits}d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart -crf 18 saida.mp4`,
        '',
      ].join('\n'),
    );
    return { kind: 'zip', blob: zip.finish(), mimeType: 'application/zip', thumbnail, lagMs: 0 };
  }
}
