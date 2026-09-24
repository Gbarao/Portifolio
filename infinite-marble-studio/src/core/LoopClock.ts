import { clamp, modulo } from './MathUtils';

export type LoopClockMode = 'preview' | 'export';

export interface LoopClockOptions {
  durationSeconds: number;
  fps: number;
  /** Relógio em milissegundos (injetável para testes). */
  now?: () => number;
  /** Quando true, o preview usa a mesma grade de frames do export (resultado idêntico). */
  snapToFrames?: boolean;
}

export const MIN_PREVIEW_SPEED = 0.25;
export const MAX_PREVIEW_SPEED = 2;

/** Conversão única usada por preview e export: garante valores bit a bit idênticos. */
export function frameToNormalizedTime(frameIndex: number, totalFrames: number): number {
  return modulo(frameIndex, totalFrames) / totalFrames;
}

export function computeTotalFrames(durationSeconds: number, fps: number): number {
  return Math.max(1, Math.round(durationSeconds * fps));
}

const defaultNow = (): number =>
  typeof performance !== 'undefined' ? performance.now() : Date.now();

/**
 * Relógio do loop. Nunca acumula delta time: o tempo é sempre derivado de uma âncora
 * (preview) ou do índice do frame (export).
 */
export class LoopClock {
  private modeValue: LoopClockMode = 'preview';
  private durationSeconds: number;
  private fps: number;
  private readonly now: () => number;
  snapToFrames: boolean;

  private playing = true;
  private speed = 1;
  private anchorWallMs: number;
  private anchorElapsedSeconds = 0;

  private exportFrameIndex = 0;
  private exportFramesPerLoop = 1;

  constructor(options: LoopClockOptions) {
    this.durationSeconds = options.durationSeconds;
    this.fps = options.fps;
    this.now = options.now ?? defaultNow;
    this.snapToFrames = options.snapToFrames ?? true;
    this.anchorWallMs = this.now();
  }

  get mode(): LoopClockMode {
    return this.modeValue;
  }

  get isPlaying(): boolean {
    return this.playing;
  }

  get previewSpeed(): number {
    return this.speed;
  }

  get loopDurationSeconds(): number {
    return this.durationSeconds;
  }

  get previewFps(): number {
    return this.fps;
  }

  /** Frames por loop na grade de preview. */
  get totalFrames(): number {
    return computeTotalFrames(this.durationSeconds, this.fps);
  }

  /** Altera duração/FPS preservando a posição normalizada atual. */
  configure(durationSeconds: number, fps: number): void {
    const t = this.getContinuousNormalizedTime();
    this.durationSeconds = durationSeconds;
    this.fps = fps;
    this.anchorElapsedSeconds = t * durationSeconds;
    this.anchorWallMs = this.now();
  }

  play(): void {
    if (this.playing) return;
    this.anchorWallMs = this.now();
    this.playing = true;
  }

  pause(): void {
    if (!this.playing) return;
    this.anchorElapsedSeconds = this.getElapsedSeconds();
    this.playing = false;
  }

  toggle(): boolean {
    if (this.playing) this.pause();
    else this.play();
    return this.playing;
  }

  reset(): void {
    this.anchorElapsedSeconds = 0;
    this.anchorWallMs = this.now();
  }

  setSpeed(speed: number): void {
    this.anchorElapsedSeconds = this.getElapsedSeconds();
    this.anchorWallMs = this.now();
    this.speed = clamp(speed, MIN_PREVIEW_SPEED, MAX_PREVIEW_SPEED);
  }

  seekNormalized(normalizedTime: number): void {
    this.anchorElapsedSeconds = modulo(normalizedTime, 1) * this.durationSeconds;
    this.anchorWallMs = this.now();
  }

  /** Tempo de loop decorrido no preview (segundos, em [0, duração)). */
  getElapsedSeconds(): number {
    const running = this.playing ? ((this.now() - this.anchorWallMs) / 1000) * this.speed : 0;
    return modulo(this.anchorElapsedSeconds + running, this.durationSeconds);
  }

  beginExport(exportFps: number): void {
    this.modeValue = 'export';
    this.exportFramesPerLoop = computeTotalFrames(this.durationSeconds, exportFps);
    this.exportFrameIndex = 0;
  }

  setFrameIndex(frameIndex: number): void {
    this.exportFrameIndex = Math.max(0, Math.floor(frameIndex));
  }

  endExport(): void {
    this.modeValue = 'preview';
    this.anchorWallMs = this.now();
  }

  getFrameIndex(): number {
    if (this.modeValue === 'export') {
      return modulo(this.exportFrameIndex, this.exportFramesPerLoop);
    }
    const total = this.totalFrames;
    // Epsilon evita que k/fps exato caia no frame k-1 por erro de ponto flutuante.
    return modulo(Math.floor(this.getElapsedSeconds() * this.fps + 1e-6), total);
  }

  /** Tempo normalizado em [0, 1). */
  getNormalizedTime(): number {
    if (this.modeValue === 'export') {
      return frameToNormalizedTime(this.exportFrameIndex, this.exportFramesPerLoop);
    }
    if (this.snapToFrames) {
      return frameToNormalizedTime(this.getFrameIndex(), this.totalFrames);
    }
    return this.getContinuousNormalizedTime();
  }

  private getContinuousNormalizedTime(): number {
    return modulo(this.getElapsedSeconds() / this.durationSeconds, 1);
  }
}

/**
 * Tempo de animação: repete a coreografia `loopCycles` vezes (inteiro) dentro do loop.
 * Periódico em normalizedTime com período 1.
 */
export function computeAnimationTime(normalizedTime: number, loopCycles: number): number {
  return modulo(normalizedTime * Math.max(1, Math.round(loopCycles)), 1);
}
