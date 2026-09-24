import { describe, expect, it } from 'vitest';
import { SeededRandom, deriveSeed, hashString, normalizeSeed } from '../core/SeededRandom';

const sequence = (seed: number, n = 20): number[] => {
  const rng = new SeededRandom(seed);
  return Array.from({ length: n }, () => rng.next());
};

describe('SeededRandom (Mulberry32)', () => {
  it('mesma seed produz a mesma sequência', () => {
    expect(sequence(12345)).toEqual(sequence(12345));
  });

  it('seeds diferentes produzem sequências diferentes', () => {
    expect(sequence(1)).not.toEqual(sequence(2));
  });

  it('next() ∈ [0, 1)', () => {
    const rng = new SeededRandom(7);
    for (let i = 0; i < 10000; i++) {
      const v = rng.next();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it('nextInt ∈ [min, max) e nextFloat ∈ [min, max)', () => {
    const rng = new SeededRandom(99);
    const seen = new Set<number>();
    for (let i = 0; i < 2000; i++) {
      const n = rng.nextInt(8, 21);
      expect(n).toBeGreaterThanOrEqual(8);
      expect(n).toBeLessThan(21);
      seen.add(n);
      const f = rng.nextFloat(-2, 3);
      expect(f).toBeGreaterThanOrEqual(-2);
      expect(f).toBeLessThan(3);
    }
    expect(seen.size).toBe(13);
    expect(rng.nextInt(5, 5)).toBe(5);
  });

  it('pick e shuffle são determinísticos', () => {
    const a = new SeededRandom(5);
    const b = new SeededRandom(5);
    expect(a.shuffle([1, 2, 3, 4, 5, 6])).toEqual(b.shuffle([1, 2, 3, 4, 5, 6]));
    expect(a.pick(['x', 'y', 'z'])).toBe(b.pick(['x', 'y', 'z']));
    expect(() => a.pick([])).toThrow();
  });

  it('seeds derivadas são estáveis e independentes', () => {
    expect(deriveSeed(10, 'colors')).toBe(deriveSeed(10, 'colors'));
    expect(deriveSeed(10, 'colors')).not.toBe(deriveSeed(10, 'path'));
    expect(deriveSeed(10, 'colors')).not.toBe(deriveSeed(11, 'colors'));
    expect(hashString('abc')).toBe(hashString('abc'));
    expect(SeededRandom.derived(3, 'a').next()).toBe(SeededRandom.derived(3, 'a').next());
  });

  it('normaliza seeds inválidas ou fora do intervalo', () => {
    expect(normalizeSeed(Number.NaN)).toBe(0);
    expect(normalizeSeed(-1)).toBe(0xffffffff);
    expect(normalizeSeed(12.9)).toBe(12);
    expect(new SeededRandom(2 ** 32 + 5).initialSeed).toBe(5);
    const next = new SeededRandom(1).nextSeed();
    expect(Number.isInteger(next)).toBe(true);
  });
});
