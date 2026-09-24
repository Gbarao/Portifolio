import type { VideoCodec, VideoEncoderId } from '../presets/PresetSchema';
import type { CaptureHost } from './CaptureHost';
import { canvasToBlob, createThumbnail } from './DownloadUtils';
import { muxWebm, type WebmChunk } from './WebmMuxer';
import { ZipWriter } from './ZipWriter';

export interface VideoExportOptions {
  width: number;
  height: number;
  fps: number;
  totalFrames: number;
  bitrateMbps: number;
  codec: VideoCodec;
  encoder: VideoEncoderId;
  /** JSON do preset incluído no ZIP de fallback. */
  presetJson: string;
}

export interface VideoExportProgress {
  frame: number;
  totalFrames: number;
  percent: number;
  elapsedMs: number;
  estimatedTotalMs: number;
  /** MediaRecorder: maior atraso em relação ao cronograma de tempo real (ms). */
  lagMs: number;
}

export type VideoExportMethod = 'mediaRecorder' | 'webCodecs' | 'pngZip';

export interface VideoExportResult {
  kind: 'webm' | 'zip';
  method: VideoExportMethod;
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

/** Retorna o mimeType suportado pelo MediaRecorder (codec pedido, VP8 como fallback) ou null. */
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

/** Configuração WebCodecs para o codec pedido (VP9 usa nível conforme a resolução). */
export function webCodecsConfig(
  codec: VideoCodec,
  width: number,
  height: number,
  fps: number,
  bitrateMbps: number,
): VideoEncoderConfig {
  const vp9Level = width * height <= 1920 * 1088 ? '41' : '51';
  return {
    codec: codec === 'vp9' ? `vp09.00.${vp9Level}.08` : 'vp8',
    width,
    height,
    framerate: fps,
    bitrate: Math.round(bitrateMbps * 1_000_000),
    latencyMode: 'quality',
  };
}

export async function isWebCodecsSupported(config: VideoEncoderConfig): Promise<boolean> {
  if (typeof VideoEncoder === 'undefined' || typeof VideoFrame === 'undefined') return false;
  try {
    const support = await VideoEncoder.isConfigSupported(config);
    return support.supported === true;
  } catch {
    return false;
  }
}

const nextAnimationFrame = (): Promise<number> =>
  new Promise((resolve) => requestAnimationFrame(resolve));

const yieldToBrowser = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 0));

/**
 * Exporta o loop frame a frame. Cada frame é renderizado a partir do índice (modo Export
 * do LoopClock), nunca do relógio real.
 *
 * - MediaRecorder (padrão): captureStream(0) + requestFrame(). O MediaRecorder carimba cada
 *   frame com o horário de captura, então o ritmo segue o requestAnimationFrame em tempo real.
 * - WebCodecs (opcional): VideoEncoder com timestamps exatos (i × 1e6 / fps) + muxer WebM
 *   próprio; independe da velocidade de renderização e roda mais rápido que o tempo real.
 * - Fallback: sequência PNG em ZIP quando nenhum encoder está disponível.
 */
export class VideoExporter {
  constructor(private readonly host: CaptureHost) {}

  async export(
    options: VideoExportOptions,
    onProgress: (progress: VideoExportProgress) => void,
    signal: AbortSignal,
  ): Promise<VideoExportResult> {
    const config = webCodecsConfig(
      options.codec,
      options.width,
      options.height,
      options.fps,
      options.bitrateMbps,
    );
    const useWebCodecs = options.encoder === 'webCodecs' && (await isWebCodecsSupported(config));
    const mimeType = getSupportedMimeType(options.codec);
    this.host.beginCapture(options.fps);
    try {
      if (useWebCodecs) return await this.recordWebCodecs(options, config, onProgress, signal);
      if (mimeType && typeof this.host.canvas.captureStream === 'function') {
        return await this.recordMediaRecorder(options, mimeType, onProgress, signal);
      }
      return await this.recordPngZip(options, onProgress, signal);
    } finally {
      this.host.endCapture();
    }
  }

  private async recordMediaRecorder(
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
    let lagMs = 0;
    let hiddenSince: number | null = null;
    // Aba oculta: pausa a gravação (o tempo pausado não entra no vídeo).
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
      while (frame < totalFrames) {
        if (signal.aborted) throw new ExportCancelledError();
        const now = await nextAnimationFrame();
        if (hiddenSince !== null) {
          if (document.hidden) continue;
          schedule += now - hiddenSince;
          hiddenSince = null;
          recorder.resume();
        }
        const due = schedule + frame * frameMs;
        if (now + 2 < due) continue;
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
        method: 'mediaRecorder',
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

  private async recordWebCodecs(
    options: VideoExportOptions,
    config: VideoEncoderConfig,
    onProgress: (progress: VideoExportProgress) => void,
    signal: AbortSignal,
  ): Promise<VideoExportResult> {
    const { fps, totalFrames } = options;
    const chunks: WebmChunk[] = [];
    let encoderError: Error | null = null;
    const encoder = new VideoEncoder({
      output: (chunk) => {
        const data = new Uint8Array(chunk.byteLength);
        chunk.copyTo(data);
        chunks.push({ data, timestampUs: chunk.timestamp, keyFrame: chunk.type === 'key' });
      },
      error: (error) => {
        encoderError = error instanceof Error ? error : new Error(String(error));
      },
    });
    encoder.configure(config);
    const frameDurationUs = 1_000_000 / fps;
    const keyInterval = Math.max(1, Math.round(fps * 2));
    const startedAt = performance.now();
    let thumbnail = '';
    try {
      for (let frame = 0; frame < totalFrames; frame++) {
        if (signal.aborted) throw new ExportCancelledError();
        if (encoderError) throw encoderError;
        this.host.renderExportFrame(frame);
        // VideoFrame lê o drawing buffer na mesma tarefa da renderização.
        const videoFrame = new VideoFrame(this.host.canvas, {
          timestamp: Math.round(frame * frameDurationUs),
          duration: Math.round(frameDurationUs),
        });
        if (frame === 0) thumbnail = createThumbnail(this.host.canvas);
        encoder.encode(videoFrame, { keyFrame: frame % keyInterval === 0 });
        videoFrame.close();
        while (encoder.encodeQueueSize > 4) await yieldToBrowser();
        if (frame % 4 === 3) await yieldToBrowser();
        const elapsedMs = performance.now() - startedAt;
        onProgress({
          frame: frame + 1,
          totalFrames,
          percent: ((frame + 1) / totalFrames) * 100,
          elapsedMs,
          estimatedTotalMs: (elapsedMs / (frame + 1)) * totalFrames,
          lagMs: 0,
        });
      }
      await encoder.flush();
      if (encoderError) throw encoderError;
    } finally {
      if (encoder.state !== 'closed') encoder.close();
    }
    chunks.sort((a, b) => a.timestampUs - b.timestampUs);
    const bytes = muxWebm(chunks, {
      codecId: config.codec === 'vp8' ? 'V_VP8' : 'V_VP9',
      width: options.width,
      height: options.height,
      frameRate: fps,
      durationMs: (totalFrames * 1000) / fps,
    });
    return {
      kind: 'webm',
      method: 'webCodecs',
      blob: new Blob([bytes as Uint8Array<ArrayBuffer>], { type: 'video/webm' }),
      mimeType: 'video/webm',
      thumbnail,
      lagMs: 0,
    };
  }

  /** Fallback: sequência PNG em ZIP (sem encoder de vídeo). */
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
      });
    }
    zip.addText('preset.json', options.presetJson);
    zip.addText(
      'LEIA-ME.txt',
      [
        'Sequência PNG gerada pelo Infinite Marble Studio (fallback sem encoder de vídeo).',
        'Converter para MP4 (opcional):',
        `ffmpeg -framerate ${options.fps} -i frame_%0${digits}d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart -crf 18 saida.mp4`,
        '',
      ].join('\n'),
    );
    return {
      kind: 'zip',
      method: 'pngZip',
      blob: zip.finish(),
      mimeType: 'application/zip',
      thumbnail,
      lagMs: 0,
    };
  }
}
