export const TAU = Math.PI * 2;

/** Módulo matemático: sempre retorna valor em [0, divisor), inclusive para entradas negativas. */
export function modulo(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}

export function clamp(value: number, min: number, max: number): number {
  return value < min ? min : value > max ? max : value;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

export function degToRad(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

export function radToDeg(radians: number): number {
  return (radians * 180) / Math.PI;
}

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

/** Verdadeiro quando `value` está a até `epsilon` de um inteiro. */
export function isNearlyInteger(value: number, epsilon = 1e-9): boolean {
  return Math.abs(value - Math.round(value)) <= epsilon;
}

export function approxEqual(a: number, b: number, epsilon = 1e-6): boolean {
  return Math.abs(a - b) <= epsilon;
}

/** Menor distância circular entre dois valores em [0, 1). */
export function circularDistance(a: number, b: number): number {
  const d = modulo(a - b, 1);
  return Math.min(d, 1 - d);
}

/** Onda senoidal periódica com número inteiro de ciclos em t ∈ [0, 1). */
export function periodicSine(t: number, cycles: number, phase = 0): number {
  return Math.sin(TAU * (t * cycles + phase));
}

/** Arredonda para `decimals` casas; normaliza −0 para 0 (JSON não preserva −0). */
export function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor || 0;
}
