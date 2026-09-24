export const MAX_SEED = 0xffffffff;

/** Converte qualquer número para um inteiro de 32 bits sem sinal (seed válida). */
export function normalizeSeed(seed: number): number {
  if (!Number.isFinite(seed)) return 0;
  return Math.trunc(seed) >>> 0;
}

/** Hash FNV-1a de 32 bits. */
export function hashString(text: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** Deriva uma seed independente para um subsistema (ex.: "marbleColors"), sem consumir o gerador principal. */
export function deriveSeed(seed: number, salt: string): number {
  let h = (normalizeSeed(seed) ^ hashString(salt)) >>> 0;
  // Finalizador do MurmurHash3 para espalhar os bits.
  h = Math.imul(h ^ (h >>> 16), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return (h ^ (h >>> 16)) >>> 0;
}

/** Gerador pseudoaleatório determinístico Mulberry32. */
export class SeededRandom {
  readonly initialSeed: number;
  private state: number;

  constructor(seed: number) {
    this.initialSeed = normalizeSeed(seed);
    this.state = this.initialSeed;
  }

  static derived(seed: number, salt: string): SeededRandom {
    return new SeededRandom(deriveSeed(seed, salt));
  }

  /** Valor em [0, 1). */
  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  /** Inteiro em [min, max). */
  nextInt(min: number, max: number): number {
    if (max <= min) return min;
    return min + Math.floor(this.next() * (max - min));
  }

  /** Float em [min, max). */
  nextFloat(min: number, max: number): number {
    return min + this.next() * (max - min);
  }

  nextBool(probability = 0.5): boolean {
    return this.next() < probability;
  }

  pick<T>(items: readonly T[]): T {
    if (items.length === 0) throw new Error('SeededRandom.pick: lista vazia');
    return items[this.nextInt(0, items.length)] as T;
  }

  /** Embaralhamento Fisher-Yates in-place. */
  shuffle<T>(items: T[]): T[] {
    for (let i = items.length - 1; i > 0; i--) {
      const j = this.nextInt(0, i + 1);
      const tmp = items[i] as T;
      items[i] = items[j] as T;
      items[j] = tmp;
    }
    return items;
  }

  /** Gera uma nova seed derivada da sequência atual. */
  nextSeed(): number {
    return Math.floor(this.next() * MAX_SEED) >>> 0;
  }
}
