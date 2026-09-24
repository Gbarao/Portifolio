import { expect } from 'vitest';

/** 1 − ε usado nos testes de fechamento de loop. */
export const END_EPSILON = 1e-6;

export function maxAbsDiff(a: readonly number[], b: readonly number[]): number {
  expect(a.length).toBe(b.length);
  let max = 0;
  for (let i = 0; i < a.length; i++)
    max = Math.max(max, Math.abs((a[i] as number) - (b[i] as number)));
  return max;
}

export function expectAllFinite(values: readonly number[]): void {
  for (const v of values) expect(Number.isFinite(v)).toBe(true);
}

/** Maior ângulo (rad) entre quaternions correspondentes (listas x,y,z,w). */
export function maxQuaternionAngle(a: readonly number[], b: readonly number[]): number {
  let max = 0;
  for (let i = 0; i < a.length; i += 4) {
    let dot = 0;
    for (let k = 0; k < 4; k++) dot += (a[i + k] as number) * (b[i + k] as number);
    const angle = 2 * Math.acos(Math.min(1, Math.abs(dot)));
    max = Math.max(max, angle);
  }
  return max;
}
