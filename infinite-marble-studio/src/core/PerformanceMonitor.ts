export type PerformanceLevel = 'good' | 'warning' | 'critical';

export interface PerformanceSnapshot {
  fps: number;
  minFps: number;
  maxFps: number;
  level: PerformanceLevel;
  sampleCount: number;
}

export const FPS_WARNING_THRESHOLD = 30;
export const FPS_CRITICAL_THRESHOLD = 20;

/** Janela deslizante de 60 frames sem alocação por frame (buffer circular). */
export class PerformanceMonitor {
  private readonly deltas: Float64Array;
  private cursor = 0;
  private count = 0;
  private lastTimestamp: number | null = null;

  constructor(readonly windowSize = 60) {
    this.deltas = new Float64Array(windowSize);
  }

  reset(): void {
    this.cursor = 0;
    this.count = 0;
    this.lastTimestamp = null;
  }

  /** Registra o timestamp (ms) de um frame renderizado. */
  recordFrame(timestampMs: number): void {
    if (this.lastTimestamp !== null) {
      const delta = timestampMs - this.lastTimestamp;
      if (delta > 0 && delta < 1000) {
        this.deltas[this.cursor] = delta;
        this.cursor = (this.cursor + 1) % this.windowSize;
        this.count = Math.min(this.count + 1, this.windowSize);
      }
    }
    this.lastTimestamp = timestampMs;
  }

  getSnapshot(): PerformanceSnapshot {
    if (this.count === 0) {
      return { fps: 0, minFps: 0, maxFps: 0, level: 'good', sampleCount: 0 };
    }
    let sum = 0;
    let maxDelta = 0;
    let minDelta = Number.POSITIVE_INFINITY;
    for (let i = 0; i < this.count; i++) {
      const d = this.deltas[i] ?? 0;
      sum += d;
      if (d > maxDelta) maxDelta = d;
      if (d < minDelta) minDelta = d;
    }
    const fps = 1000 / (sum / this.count);
    const level: PerformanceLevel =
      fps < FPS_CRITICAL_THRESHOLD ? 'critical' : fps < FPS_WARNING_THRESHOLD ? 'warning' : 'good';
    return {
      fps,
      minFps: 1000 / maxDelta,
      maxFps: 1000 / minDelta,
      level,
      sampleCount: this.count,
    };
  }
}

export interface HeavinessInput {
  marbleCount: number;
  shadowsEnabled: boolean;
  trackSegments: number;
  shadowResolution: number;
  pixelRatio: number;
}

/** Recomendações automáticas quando o FPS está baixo ou a configuração é pesada. */
export function getPerformanceRecommendations(
  input: HeavinessInput,
  level: PerformanceLevel,
): string[] {
  const tips: string[] = [];
  if (input.marbleCount > 150 && input.shadowsEnabled) {
    tips.push('Configuração pesada: mais de 150 bolinhas com sombras ativas.');
  }
  if (level === 'good') return tips;
  if (input.shadowsEnabled) tips.push('Desative as sombras ou reduza a resolução de sombra.');
  if (input.shadowResolution > 1024) tips.push('Use resolução de sombra 1024 ou 512.');
  if (input.marbleCount > 100) tips.push('Reduza a quantidade de bolinhas.');
  if (input.trackSegments > 200) tips.push('Reduza os segmentos do trilho.');
  if (input.pixelRatio > 1) tips.push('Reduza o pixel ratio do preview para 1.');
  return tips;
}
