import { modulo } from './MathUtils';
import { SeededRandom } from './SeededRandom';

/**
 * Ruído gradiente 1D (Perlin) periódico: sample(t) tem período exato 1 em t.
 * Usado para variações orgânicas que precisam fechar o loop sem emenda.
 */
export class PeriodicNoise {
  private readonly gradients: Float64Array;
  readonly period: number;

  constructor(seed: number, period = 8) {
    this.period = Math.max(2, Math.floor(period));
    this.gradients = new Float64Array(this.period);
    const rng = new SeededRandom(seed);
    for (let i = 0; i < this.period; i++) {
      this.gradients[i] = rng.nextFloat(-1, 1);
    }
  }

  /** Valor aproximadamente em [-1, 1]; sample(t) === sample(t + 1). */
  sample(t: number): number {
    const x = modulo(t, 1) * this.period;
    const cell = Math.floor(x);
    const f = x - cell;
    const i0 = cell % this.period;
    const i1 = (i0 + 1) % this.period;
    const g0 = this.gradients[i0] ?? 0;
    const g1 = this.gradients[i1] ?? 0;
    const fade = f * f * f * (f * (f * 6 - 15) + 10);
    const a = g0 * f;
    const b = g1 * (f - 1);
    return (a + (b - a) * fade) * 2;
  }
}
