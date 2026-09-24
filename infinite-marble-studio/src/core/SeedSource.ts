import { MAX_SEED, normalizeSeed } from './SeededRandom';

/**
 * Único ponto não determinístico da aplicação: escolhe uma seed nova quando o usuário
 * pede "Randomizar". Toda geração procedural é derivada exclusivamente dessa seed.
 */
export function createRandomSeed(): number {
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const buffer = new Uint32Array(1);
    crypto.getRandomValues(buffer);
    return normalizeSeed(buffer[0] ?? 0);
  }
  // Fallback sem Math.random: relógio de alta resolução embaralhado.
  const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
  return normalizeSeed((now * 1000) % MAX_SEED);
}
